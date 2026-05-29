# Scheduled job that runs the nightly options scan and dispatches the morning brief email.
import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from data.market_data import get_current_price, get_iv_rank
from data.news_fetcher import fetch_news_for_ticker
from data.options_fetcher import fetch_unusual_options_flow
from db.database import async_session
from db.models import FlowScan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _enrich_ticker(flow_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Augment a single ticker's flow dict with live price, IV rank, and news.

    Price, IV rank, and news are fetched concurrently via asyncio.gather.
    If the price fetch fails the ticker is skipped entirely (price is required
    for a meaningful scan row).  IV rank and news failures are non-fatal —
    the row is stored with None / empty list instead.

    Args:
        flow_data: One item returned by fetch_unusual_options_flow().

    Returns:
        Enriched dict, or None if a critical fetch failed.
    """
    ticker: str = flow_data["ticker"]

    price_result, iv_result, news_result = await asyncio.gather(
        get_current_price(ticker),
        get_iv_rank(ticker),
        fetch_news_for_ticker(ticker),
        return_exceptions=True,
    )

    # Treat exceptions from gather the same as a None return
    price: float | None = None if isinstance(price_result, Exception) else price_result
    iv_rank: float | None = None if isinstance(iv_result, Exception) else iv_result
    news: list[dict] = [] if isinstance(news_result, Exception) else (news_result or [])

    if isinstance(price_result, Exception):
        logger.error("_enrich_ticker(%s): get_current_price raised — %s", ticker, price_result)
    if isinstance(iv_result, Exception):
        logger.error("_enrich_ticker(%s): get_iv_rank raised — %s", ticker, iv_result)
    if isinstance(news_result, Exception):
        logger.error("_enrich_ticker(%s): fetch_news_for_ticker raised — %s", ticker, news_result)

    if price is None:
        logger.warning(
            "_enrich_ticker(%s): skipping — could not fetch current price.", ticker
        )
        return None

    return {
        # --- flow fields from options_fetcher ---
        "ticker":         ticker,
        "call_volume":    flow_data.get("call_volume"),
        "put_volume":     flow_data.get("put_volume"),
        "oi_ratio":       flow_data.get("oi_ratio"),
        "call_put_ratio": flow_data.get("call_put_ratio"),
        "avg_strike":     flow_data.get("avg_strike"),
        "avg_expiry":     flow_data.get("avg_expiry"),   # string "YYYY-MM-DD"
        # --- enriched fields ---
        "iv_rank":        iv_rank,
        "price_at_scan":  price,
        "news":           news,
    }


def _parse_date(value: Any) -> date | None:
    """Safely coerce a value to a date object, or return None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_daily_scan() -> list[int]:
    """
    Orchestrate the full nightly options scan pipeline.

    Steps
    ─────
    1. Fetch the top-10 unusual-flow tickers via fetch_unusual_options_flow().
    2. Concurrently enrich each ticker with live price, IV rank, and news.
    3. Persist each enriched ticker as a FlowScan row in the database.
    4. Return the list of inserted flow_scan IDs.

    Returns:
        List of integer primary-key IDs for every successfully inserted row.
    """
    scan_start = time.perf_counter()
    logger.info("run_daily_scan: starting at %s", datetime.now(tz=timezone.utc).isoformat())

    # ── Step 1: options flow ────────────────────────────────────────────────
    logger.info("run_daily_scan: fetching unusual options flow…")
    try:
        flow_results = await fetch_unusual_options_flow()
    except Exception as exc:
        logger.error("run_daily_scan: fetch_unusual_options_flow failed — %s", exc, exc_info=True)
        return []

    if not flow_results:
        logger.warning("run_daily_scan: no flow results returned — aborting scan.")
        return []

    logger.info("run_daily_scan: received %d tickers from options flow scan.", len(flow_results))

    # ── Step 2: enrich each ticker concurrently ─────────────────────────────
    logger.info("run_daily_scan: enriching tickers with price, IV rank, and news…")
    enriched_results = await asyncio.gather(
        *[_enrich_ticker(flow_data) for flow_data in flow_results],
        return_exceptions=True,
    )

    valid_enriched: list[dict[str, Any]] = []
    for i, result in enumerate(enriched_results):
        ticker = flow_results[i]["ticker"]
        if isinstance(result, Exception):
            logger.error("run_daily_scan: _enrich_ticker(%s) raised — %s", ticker, result)
        elif result is None:
            logger.warning("run_daily_scan: %s skipped (enrichment returned None).", ticker)
        else:
            valid_enriched.append(result)

    if not valid_enriched:
        logger.error("run_daily_scan: no tickers survived enrichment — nothing to store.")
        return []

    logger.info("run_daily_scan: %d/%d tickers ready for storage.", len(valid_enriched), len(flow_results))

    # ── Step 3: persist to database ─────────────────────────────────────────
    scan_date_today = date.today()
    inserted_ids: list[int] = []

    async with async_session() as session:
        try:
            for enriched in valid_enriched:
                ticker = enriched["ticker"]
                scan = FlowScan(
                    ticker         = ticker,
                    scan_date      = scan_date_today,
                    call_volume    = enriched.get("call_volume"),
                    put_volume     = enriched.get("put_volume"),
                    oi_ratio       = enriched.get("oi_ratio"),
                    avg_strike     = enriched.get("avg_strike"),
                    avg_expiry     = _parse_date(enriched.get("avg_expiry")),
                    iv_rank        = enriched.get("iv_rank"),
                    price_at_scan  = enriched.get("price_at_scan"),
                    # Store the full enriched payload (including news) for the AI agent
                    raw_data       = enriched,
                )
                session.add(scan)
                # Flush after each add to populate the autoincrement ID
                await session.flush()

                inserted_ids.append(scan.id)
                logger.info(
                    "run_daily_scan: stored %-6s | oi_ratio=%.4f | price=%.2f | id=%d",
                    ticker,
                    enriched.get("oi_ratio") or 0.0,
                    enriched.get("price_at_scan") or 0.0,
                    scan.id,
                )

            await session.commit()

        except Exception as exc:
            await session.rollback()
            logger.error(
                "run_daily_scan: database error — rolled back all inserts. Error: %s",
                exc, exc_info=True,
            )
            return []

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - scan_start
    logger.info(
        "run_daily_scan: complete — %d row(s) inserted in %.2fs.",
        len(inserted_ids), elapsed,
    )

    return inserted_ids


# ---------------------------------------------------------------------------
# CLI entry point — test the full pipeline from the terminal:
#   python backend/scheduler/daily_scan.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Ensure 'backend/' is on sys.path so sibling packages resolve correctly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ids = asyncio.run(run_daily_scan())
    print(f"\nInserted {len(ids)} flow scan row(s): {ids}")

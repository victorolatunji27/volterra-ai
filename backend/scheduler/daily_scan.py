# Scheduled job that runs the nightly options scan and dispatches the morning brief email.
import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from data.market_data import get_current_price, get_iv_rank
from data.news_fetcher import fetch_news_for_ticker
from data.options_fetcher import fetch_options_flow_yfinance
from db.database import async_session
from db.models import FlowScan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: Any) -> date | None:
    """Safely coerce a string or date to a date object, or return None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


async def _enrich_ticker(flow_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Augment one flow dict with live price, IV rank, and news fetched concurrently.

    Price, IV rank, and news are gathered in parallel.  A missing price is the
    only hard failure — IV rank and news degrade gracefully to None / [].

    Returns the enriched dict, or None if the current price could not be fetched.
    """
    ticker: str = flow_data["ticker"]

    price_res, iv_res, news_res = await asyncio.gather(
        get_current_price(ticker),
        get_iv_rank(ticker),
        fetch_news_for_ticker(ticker),
        return_exceptions=True,
    )

    price:      float | None   = None if isinstance(price_res, Exception) else price_res
    iv_rank:    float | None   = None if isinstance(iv_res,    Exception) else iv_res
    news:       list[dict]     = []   if isinstance(news_res,  Exception) else (news_res or [])

    if isinstance(price_res, Exception):
        logger.error("_enrich_ticker(%s): get_current_price raised — %s", ticker, price_res)
    if isinstance(iv_res, Exception):
        logger.error("_enrich_ticker(%s): get_iv_rank raised — %s", ticker, iv_res)
    if isinstance(news_res, Exception):
        logger.error("_enrich_ticker(%s): fetch_news_for_ticker raised — %s", ticker, news_res)

    if price is None:
        logger.warning("_enrich_ticker(%s): no price available — skipping.", ticker)
        return None

    return {
        "ticker":         ticker,
        "call_volume":    flow_data.get("call_volume"),
        "put_volume":     flow_data.get("put_volume"),
        "oi_ratio":       flow_data.get("oi_ratio"),
        "call_put_ratio": flow_data.get("call_put_ratio"),
        "avg_strike":     flow_data.get("avg_strike"),
        "iv_rank":        iv_rank,
        "price_at_scan":  price,
        "news":           news,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_daily_scan() -> list[int]:
    """
    Orchestrate the full nightly options scan pipeline.

    Steps
    ─────
    1. Fetch the top-10 unusual-flow tickers via fetch_options_flow_yfinance()
       (yfinance — no API key required).
    2. For each ticker, concurrently fetch current price, IV rank, and news.
       Each ticker is wrapped in its own try/except so one failure never
       stops the rest.
    3. Insert a FlowScan row for every successfully enriched ticker.
    4. Return the list of inserted row IDs.

    Returns:
        List of integer primary-key IDs for every successfully inserted row.
    """
    scan_start = time.perf_counter()
    logger.info("run_daily_scan: starting at %s UTC", datetime.now(tz=timezone.utc).isoformat())

    # ── Step 1: options flow via yfinance ───────────────────────────────────
    logger.info("run_daily_scan: fetching unusual options flow (yfinance)…")
    try:
        flow_results = await fetch_options_flow_yfinance()
    except Exception as exc:
        logger.error("run_daily_scan: fetch_options_flow_yfinance failed — %s", exc, exc_info=True)
        return []

    if not flow_results:
        logger.warning("run_daily_scan: no flow results returned — aborting.")
        return []

    logger.info("run_daily_scan: %d tickers received from options flow scan.", len(flow_results))

    # ── Step 2: enrich each ticker (per-ticker try/except) ──────────────────
    logger.info("run_daily_scan: enriching tickers with price, IV rank, and news…")

    enriched_batch: list[dict[str, Any]] = []

    for flow_data in flow_results:
        ticker = flow_data["ticker"]
        try:
            enriched = await _enrich_ticker(flow_data)
            if enriched is not None:
                enriched_batch.append(enriched)
            else:
                logger.warning("run_daily_scan: %s skipped (enrichment returned None).", ticker)
        except Exception as exc:
            logger.error(
                "run_daily_scan: %s enrichment raised an unhandled error — %s. Skipping.",
                ticker, exc, exc_info=True,
            )

    if not enriched_batch:
        logger.error("run_daily_scan: no tickers survived enrichment — nothing to store.")
        return []

    logger.info(
        "run_daily_scan: %d/%d tickers ready for storage.",
        len(enriched_batch), len(flow_results),
    )

    # ── Step 3: persist to database ─────────────────────────────────────────
    scan_date_today = date.today()
    inserted_ids: list[int] = []

    async with async_session() as session:
        for enriched in enriched_batch:
            ticker = enriched["ticker"]
            try:
                scan = FlowScan(
                    ticker        = ticker,
                    scan_date     = scan_date_today,
                    call_volume   = enriched.get("call_volume"),
                    put_volume    = enriched.get("put_volume"),
                    oi_ratio      = enriched.get("oi_ratio"),
                    avg_strike    = enriched.get("avg_strike"),
                    # avg_expiry comes from the raw flow data, not the enriched dict
                    avg_expiry    = _parse_date(
                        next(
                            (f.get("avg_expiry") for f in flow_results if f["ticker"] == ticker),
                            None,
                        )
                    ),
                    iv_rank       = enriched.get("iv_rank"),
                    price_at_scan = enriched.get("price_at_scan"),
                    raw_data      = enriched,   # full payload stored for AI agent use
                )
                session.add(scan)
                await session.flush()           # populate autoincrement id before commit
                inserted_ids.append(scan.id)

                logger.info(
                    "run_daily_scan: stored %-6s | oi_ratio=%.4f | price=%s | id=%d",
                    ticker,
                    enriched.get("oi_ratio") or 0.0,
                    f"{enriched['price_at_scan']:.2f}" if enriched.get("price_at_scan") else "N/A",
                    scan.id,
                )

            except Exception as exc:
                logger.error(
                    "run_daily_scan: DB insert failed for %s — %s. Skipping.",
                    ticker, exc, exc_info=True,
                )
                await session.rollback()
                continue

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("run_daily_scan: final commit failed — %s", exc, exc_info=True)
            return []

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - scan_start
    logger.info(
        "run_daily_scan: complete — %d/%d rows inserted in %.2fs.",
        len(inserted_ids), len(flow_results), elapsed,
    )

    return inserted_ids


# ---------------------------------------------------------------------------
# CLI entry point
#   python backend/scheduler/daily_scan.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add backend/ to sys.path so sibling package imports resolve correctly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ids = asyncio.run(run_daily_scan())
    print(f"\nInserted {len(ids)} flow scan row(s): {ids}")

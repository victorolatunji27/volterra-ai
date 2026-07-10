# Scheduled job that runs the nightly options scan and dispatches the morning brief email.
import asyncio
import logging
import sys
import time

import sentry_sdk
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# When run directly (python backend/scheduler/daily_scan.py), add backend/ to
# sys.path BEFORE the project imports below, or they fail to resolve.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from agents.flow_analyzer import analyze_flow, store_summary, tag_strategy
from agents.journal_agent import generate_weekly_review
from agents.news_fetcher import synthesize_news
from data.market_data import get_current_price, get_iv_rank
from data.news_fetcher import fetch_news_for_ticker
from data.options_fetcher import fetch_options_flow_yfinance
from db.database import async_session
from db.models import AiSummary, AlertLog, DigestLog, FlowScan, UserProfile
from mailer.alerts import build_alert_subject, build_alert_text, send_alert_email
from mailer.digest import build_digest_html, build_digest_subject, send_digest

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


def validate_flow_scan(data: dict) -> bool:
    """
    Sanity-check one enriched flow dict before it is stored.

    Requires: positive oi_ratio, non-negative integer volumes, positive
    price_at_scan, and a non-empty ticker string.
    """
    if not isinstance(data, dict):
        return False

    ticker = data.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return False

    oi_ratio = data.get("oi_ratio")
    if not isinstance(oi_ratio, (int, float)) or isinstance(oi_ratio, bool) or oi_ratio <= 0:
        return False

    for key in ("call_volume", "put_volume"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return False

    price = data.get("price_at_scan")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        return False

    return True


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


async def _create_ai_summary(scan_id: int, enriched: dict[str, Any]) -> int | None:
    """
    Run the AI agents for one stored flow scan and persist the result.

    Pipeline: analyze_flow → synthesize_news → merge catalyst into the
    setup_summary → tag_strategy → store_summary. Returns the new
    ai_summaries row ID, or None when analysis failed.
    """
    ticker = enriched["ticker"]

    analysis = await analyze_flow({
        k: enriched.get(k)
        for k in ("ticker", "call_volume", "put_volume", "oi_ratio",
                  "call_put_ratio", "avg_strike", "iv_rank", "price_at_scan")
    })
    if analysis is None:
        logger.warning("_create_ai_summary(%s): analyze_flow returned None.", ticker)
        return None

    news_summary = await synthesize_news(ticker, enriched.get("news") or [])

    # Merge the news catalyst into the setup summary when both exist
    catalyst_note = (news_summary or {}).get("catalyst_note")
    if catalyst_note and analysis.get("setup_summary"):
        analysis["setup_summary"] = f"{analysis['setup_summary']} Catalyst: {catalyst_note}"

    analysis["strategy_tags"] = await tag_strategy({
        "flow_scan_id":   scan_id,
        "setup_summary":  analysis.get("setup_summary", ""),
        "oi_ratio":       enriched.get("oi_ratio"),
        "call_put_ratio": enriched.get("call_put_ratio"),
        "iv_rank":        enriched.get("iv_rank"),
    })

    async with async_session() as session:
        summary_id = await store_summary(scan_id, analysis, news_summary, session)

    logger.info(
        "_create_ai_summary(%s): ai_summary id=%d created (tags=%s).",
        ticker, summary_id, analysis["strategy_tags"],
    )
    return summary_id


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
    3. Validate and insert a FlowScan row for every successfully enriched ticker.
    4. Run the AI agents (flow analysis, news synthesis, strategy tagging)
       for each stored scan and persist the ai_summaries rows.
    5. Return the list of inserted flow_scan IDs.

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
            if enriched is None:
                logger.warning("run_daily_scan: %s skipped (enrichment returned None).", ticker)
            elif not validate_flow_scan(enriched):
                logger.warning("run_daily_scan: %s skipped (failed validation): %r", ticker, enriched)
            else:
                enriched_batch.append(enriched)
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
    inserted: list[tuple[int, dict[str, Any]]] = []

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
                inserted.append((scan.id, enriched))

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

    # ── Step 4: AI summaries (per-ticker try/except) ────────────────────────
    logger.info("run_daily_scan: generating AI summaries for %d scan(s)…", len(inserted))

    summary_count = 0
    for scan_id, enriched in inserted:
        try:
            if await _create_ai_summary(scan_id, enriched) is not None:
                summary_count += 1
        except Exception as exc:
            logger.error(
                "run_daily_scan: AI summary failed for %s (scan id=%d) — %s. Skipping.",
                enriched["ticker"], scan_id, exc, exc_info=True,
            )

    # ── Summary ─────────────────────────────────────────────────────────────
    inserted_ids = [scan_id for scan_id, _ in inserted]
    elapsed = time.perf_counter() - scan_start
    logger.info(
        "run_daily_scan: complete — %d/%d rows inserted, %d AI summaries, in %.2fs.",
        len(inserted_ids), len(flow_results), summary_count, elapsed,
    )

    return inserted_ids


# ---------------------------------------------------------------------------
# Digest email
# ---------------------------------------------------------------------------

async def _todays_scans_with_summaries(session, limit: int = 5) -> list[dict[str, Any]]:
    """Return today's top scans (by oi_ratio) merged with their latest AI summary."""
    scans = (
        await session.execute(
            select(FlowScan)
            .where(FlowScan.scan_date == date.today())
            .order_by(FlowScan.oi_ratio.desc())
            .limit(limit)
        )
    ).scalars().all()

    results: list[dict[str, Any]] = []
    for scan in scans:
        summary = (
            await session.execute(
                select(AiSummary)
                .where(AiSummary.flow_scan_id == scan.id)
                .order_by(AiSummary.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        call_put_ratio = (scan.raw_data or {}).get("call_put_ratio")
        results.append({
            "ticker":         scan.ticker,
            "price_at_scan":  scan.price_at_scan,
            "oi_ratio":       scan.oi_ratio,
            "call_put_ratio": call_put_ratio,
            "setup_summary":  summary.setup_summary if summary else None,
            "risk_note":      summary.risk_note if summary else None,
            "strategy_tags":  (summary.strategy_tags or []) if summary else [],
        })
    return results


async def compose_and_send_digest() -> bool:
    """
    Build and send the morning-brief email to eligible users, then log it.

    Eligible recipients: pro-tier users, plus free users within their first
    30 days. Returns True when the digest was sent successfully.
    """
    async with async_session() as session:
        scans = await _todays_scans_with_summaries(session, limit=5)
        if not scans:
            logger.warning("compose_and_send_digest: no scans for today — skipping send.")
            return False

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        users = (
            await session.execute(
                select(UserProfile).where(
                    (UserProfile.tier == "pro") | (UserProfile.created_at > cutoff)
                )
            )
        ).scalars().all()
        recipients = [u.email for u in users if u.email]

        if not recipients:
            logger.warning("compose_and_send_digest: no eligible recipients — skipping send.")
            return False

        html = build_digest_html(scans)
        subject = build_digest_subject()

        sent = send_digest(recipients, html, subject)
        if not sent:
            logger.error("compose_and_send_digest: send_digest reported failure.")
            # The Resend SDK path only surfaces success/failure, not a status
            # code — report the batch failure with its blast radius.
            sentry_sdk.capture_message(
                f"Resend digest send failed for {len(recipients)} recipient(s)",
                level="error",
            )
            return False

        session.add(DigestLog(
            recipient_count=len(recipients),
            tickers_included=[s["ticker"] for s in scans],
        ))
        await session.commit()

    logger.info(
        "compose_and_send_digest: sent digest with %d ticker(s) to %d recipient(s).",
        len(scans), len(recipients),
    )
    return True


# ---------------------------------------------------------------------------
# Strategy alerts
# ---------------------------------------------------------------------------

async def match_alerts() -> int:
    """
    Record strategy-match alerts for the day.

    For every user with non-empty strategy_tags, find today's scans whose AI
    summary strategy_tags intersect the user's tags, write a single alert_log
    row per matched user listing the matched tickers, and email the matched
    setups to the user.

    The alert_log row is recorded regardless of email outcome — a bounced or
    unconfigured send is logged, not raised, so the match record is never lost.
    Returns the number of alert_log rows written.
    """
    async with async_session() as session:
        users = (
            await session.execute(
                select(UserProfile).where(
                    UserProfile.strategy_tags.isnot(None),
                    func.cardinality(UserProfile.strategy_tags) > 0,
                )
            )
        ).scalars().all()

        if not users:
            logger.info("match_alerts: no users with strategy tags.")
            return 0

        scans = await _todays_scans_with_summaries(session, limit=10)
        tagged = [s for s in scans if s["strategy_tags"]]
        if not tagged:
            logger.info("match_alerts: no tagged summaries today.")
            return 0

        alerts_written = 0
        for user in users:
            user_tags = set(user.strategy_tags or [])
            matches = [s for s in tagged if user_tags & set(s["strategy_tags"])]
            if not matches:
                continue

            matched_tickers = [s["ticker"] for s in matches]
            session.add(AlertLog(user_id=user.id, tickers=matched_tickers))
            alerts_written += 1

            # Plain-text alert email via the Resend API (best-effort — a
            # failed send is logged + captured to Sentry inside
            # send_alert_email and never blocks the record or the scan).
            sent = await send_alert_email(
                user.email,
                build_alert_subject(matched_tickers),
                build_alert_text(matches),
            )
            if not sent:
                logger.error("match_alerts: alert email send failed for %s.", user.email)

        await session.commit()

    logger.info("match_alerts: wrote %d alert_log row(s).", alerts_written)
    return alerts_written


# ---------------------------------------------------------------------------
# Weekly AI reviews
# ---------------------------------------------------------------------------

async def run_weekly_reviews() -> int:
    """
    Generate (and cache) the weekly AI review for every user.

    generate_weekly_review() itself skips users with fewer than 3 resolved
    trades this week, so this simply iterates all user_profiles with a
    per-user try/except. Returns the number of non-empty reviews produced.
    """
    async with async_session() as session:
        users = (await session.execute(select(UserProfile))).scalars().all()

        generated = 0
        for user in users:
            try:
                review = await generate_weekly_review(user.id, session)
                if review.get("headline"):
                    generated += 1
            except Exception as exc:
                logger.error(
                    "run_weekly_reviews: failed for user %s — %s. Skipping.",
                    user.id, exc, exc_info=True,
                )

    logger.info(
        "run_weekly_reviews: %d review(s) generated across %d user(s).",
        generated, len(users),
    )
    return generated


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def initialize_scheduler():
    """
    Start the in-process APScheduler:
    06:30 UTC weekday scan, 06:45 UTC digest, 07:15 UTC strategy alerts,
    and 08:00 UTC Sunday weekly AI reviews.

    NOTE — Railway deployment: replace this with Railway Cron Jobs invoking
    `python scheduler/daily_scan.py` (and a digest entry point) instead.
    Railway Cron Jobs survive redeploys; an in-process APScheduler loses any
    job that is mid-flight when the process restarts.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_scan,
        CronTrigger(day_of_week="mon-fri", hour=6, minute=30),
        id="daily_scan",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        compose_and_send_digest,
        CronTrigger(day_of_week="mon-fri", hour=6, minute=45),
        id="daily_digest",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        match_alerts,
        CronTrigger(day_of_week="mon-fri", hour=7, minute=15),
        id="match_alerts",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_weekly_reviews,
        CronTrigger(day_of_week="sun", hour=8, minute=0),
        id="weekly_reviews",
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("initialize_scheduler: APScheduler started with 4 jobs (UTC).")
    return scheduler


# ---------------------------------------------------------------------------
# CLI entry point
#   python backend/scheduler/daily_scan.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ids = asyncio.run(run_daily_scan())
    print(f"\nInserted {len(ids)} flow scan row(s): {ids}")

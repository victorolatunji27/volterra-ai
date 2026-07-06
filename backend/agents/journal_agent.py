# Agent that generates and updates trade journal entries with AI-driven post-trade analysis.
import json
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import sentry_sdk
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.flow_analyzer import _call_claude, _parse_json_block
from cache import cache_get_json, cache_set_json
from db.models import JournalEntry

load_dotenv()

logger = logging.getLogger(__name__)

REVIEW_MODEL = "claude-sonnet-4-6"
REVIEW_CACHE_TTL = 604800  # 7 days
MIN_RESOLVED_TRADES = 3

RESOLVED_OUTCOMES = ("win", "loss", "scratch")

REVIEW_KEYS = {"headline", "bullets", "generated_at"}

REVIEW_SYSTEM_PROMPT = (
    "You are a performance coach reviewing a trader's week. Given their "
    "resolved trades, write a 3-5 sentence recap: what worked, what didn't, "
    "and one specific pattern to act on. Be direct. No fluff. Return JSON: "
    "{headline: str, bullets: [str, str, str], generated_at: str (ISO date)}"
)

EMPTY_REVIEW: dict = {"headline": None, "bullets": [], "generated_at": None}


def _iso_week(today: date | None = None) -> str:
    """Return the ISO week label for cache keys, e.g. '2026-W27'."""
    iso = (today or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def generate_weekly_review(user_id: UUID, db: AsyncSession) -> dict:
    """
    Produce a plain-English weekly recap of one user's resolved trades.

    Reads the user's resolved journal_entries from the last 7 days and asks
    Claude for {headline, bullets[3], generated_at}. Results are cached in
    Redis under weekly_review:{user_id}:{iso_week} for 7 days, so the Sunday
    scheduler run pre-warms what the API route serves all week.

    Returns EMPTY_REVIEW (headline/generated_at None, bullets []) when the
    user has fewer than MIN_RESOLVED_TRADES resolved trades this week —
    Claude is never called in that case — or when the model response cannot
    be parsed.
    """
    cache_key = f"weekly_review:{user_id}:{_iso_week()}"
    cached = await cache_get_json(cache_key)
    if isinstance(cached, dict):
        return cached

    since = datetime.now(tz=timezone.utc) - timedelta(days=7)
    rows = (
        await db.execute(
            select(
                JournalEntry.ticker,
                JournalEntry.strategy_type,
                JournalEntry.outcome,
                JournalEntry.outcome_pnl_pct,
            ).where(
                JournalEntry.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
                JournalEntry.outcome.in_(RESOLVED_OUTCOMES),
                JournalEntry.resolved_at.isnot(None),
                JournalEntry.resolved_at >= since,
            )
        )
    ).all()

    if len(rows) < MIN_RESOLVED_TRADES:
        logger.info(
            "generate_weekly_review(%s): only %d resolved trade(s) this week — skipping Claude.",
            user_id, len(rows),
        )
        return dict(EMPTY_REVIEW)

    trades = [
        {
            "ticker": r.ticker,
            "strategy_type": r.strategy_type,
            "outcome": r.outcome,
            "outcome_pnl_pct": r.outcome_pnl_pct,
        }
        for r in rows
    ]

    sentry_sdk.add_breadcrumb(
        category="agent", message=f"Generating weekly review for {user_id}", level="info"
    )
    try:
        raw, tokens_in, tokens_out = await _call_claude(
            REVIEW_SYSTEM_PROMPT,
            json.dumps(trades),
            temperature=0.3,
            max_tokens=600,
            model=REVIEW_MODEL,
        )
    except Exception as exc:
        logger.error(
            "generate_weekly_review(%s): Claude call failed — %s", user_id, exc, exc_info=True
        )
        return dict(EMPTY_REVIEW)

    result = _parse_json_block(raw)
    if not isinstance(result, dict) or not REVIEW_KEYS <= result.keys():
        logger.error(
            "generate_weekly_review(%s): invalid JSON response: %r", user_id, raw[:300]
        )
        return dict(EMPTY_REVIEW)

    await cache_set_json(cache_key, result, ttl_seconds=REVIEW_CACHE_TTL)

    logger.info(
        "generate_weekly_review(%s): review generated from %d trade(s) | tokens_in=%d | tokens_out=%d",
        user_id, len(trades), tokens_in, tokens_out,
    )
    return result

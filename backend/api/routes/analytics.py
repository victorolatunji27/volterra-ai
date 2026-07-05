# Router for journal analytics endpoints — summary stats, per-strategy/ticker breakdowns, equity curve.
#
# This is the single home for all analytics: the former GET /api/journal/analytics
# combined endpoint was consolidated here. Each section is its own endpoint and
# is cached per user in Redis (1h TTL); the cache is invalidated when a journal
# outcome changes via invalidate_analytics_cache().
from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from cache import cache_delete, cache_get_json, cache_set_json
from db.database import get_db
from db.models import JournalEntry, UserProfile

router = APIRouter(tags=["analytics"])

# A trade is "resolved" once it has a non-pending outcome.
RESOLVED_OUTCOMES = ("win", "loss", "scratch")

ANALYTICS_CACHE_TTL = 3600
_CACHE_SECTIONS = ("summary", "by_strategy", "by_ticker", "equity_curve")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SetupExtreme(BaseModel):
    ticker: str
    pnl_pct: float


class AnalyticsSummaryResponse(BaseModel):
    total_trades: int
    resolved_trades: int
    win_rate: float
    avg_pnl_pct: float
    best_setup: SetupExtreme | None = None
    worst_setup: SetupExtreme | None = None


class StrategyBreakdown(BaseModel):
    strategy_type: str
    trade_count: int
    win_rate: float
    avg_pnl_pct: float


class TickerBreakdown(BaseModel):
    ticker: str
    trade_count: int
    win_rate: float


class EquityPoint(BaseModel):
    date: date
    cumulative_pnl_pct: float


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(user_id, section: str) -> str:
    return f"analytics:{section}:{user_id}"


async def invalidate_analytics_cache(user_id) -> None:
    """Drop every cached analytics section for a user (call when an outcome changes)."""
    for section in _CACHE_SECTIONS:
        await cache_delete(_cache_key(user_id, section))


async def _store(key: str, payload):
    """Cache a JSON-able payload for the analytics TTL and return it."""
    await cache_set_json(key, payload, ttl_seconds=ANALYTICS_CACHE_TTL)
    return payload


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _resolved_filter(user_id):
    """Filter clause: this user's non-deleted, non-pending journal entries."""
    return (
        JournalEntry.user_id == user_id,
        JournalEntry.deleted_at.is_(None),
        JournalEntry.outcome.in_(RESOLVED_OUTCOMES),
    )


def _win_rate(wins: int, resolved: int) -> float:
    return round(wins / resolved * 100, 1) if resolved else 0.0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AnalyticsSummaryResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_summary(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overall performance: totals, win rate, average P&L, and best/worst setups."""
    key = _cache_key(user.id, "summary")
    cached = await cache_get_json(key)
    if cached is not None:
        return cached

    total_trades = (
        await db.execute(
            select(func.count()).where(
                JournalEntry.user_id == user.id,
                JournalEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    # Counts and average P&L across resolved trades (pending excluded by filter).
    row = (
        await db.execute(
            select(
                func.count().label("resolved"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
                func.avg(JournalEntry.outcome_pnl_pct).label("avg_pnl"),
            ).where(*_resolved_filter(user.id))
        )
    ).one()

    resolved = row.resolved or 0
    if not resolved:
        # No resolved trades — return a zeroed summary rather than erroring.
        model = AnalyticsSummaryResponse(
            total_trades=total_trades,
            resolved_trades=0,
            win_rate=0.0,
            avg_pnl_pct=0.0,
        )
        return await _store(key, model.model_dump(mode="json"))

    best_row = (
        await db.execute(
            select(JournalEntry.ticker, JournalEntry.outcome_pnl_pct)
            .where(*_resolved_filter(user.id), JournalEntry.outcome_pnl_pct.isnot(None))
            .order_by(JournalEntry.outcome_pnl_pct.desc())
            .limit(1)
        )
    ).first()
    worst_row = (
        await db.execute(
            select(JournalEntry.ticker, JournalEntry.outcome_pnl_pct)
            .where(*_resolved_filter(user.id), JournalEntry.outcome_pnl_pct.isnot(None))
            .order_by(JournalEntry.outcome_pnl_pct.asc())
            .limit(1)
        )
    ).first()

    model = AnalyticsSummaryResponse(
        total_trades=total_trades,
        resolved_trades=resolved,
        win_rate=_win_rate(int(row.wins or 0), resolved),
        avg_pnl_pct=round(float(row.avg_pnl), 2) if row.avg_pnl is not None else 0.0,
        best_setup=(
            SetupExtreme(ticker=best_row.ticker, pnl_pct=round(float(best_row.outcome_pnl_pct), 2))
            if best_row else None
        ),
        worst_setup=(
            SetupExtreme(ticker=worst_row.ticker, pnl_pct=round(float(worst_row.outcome_pnl_pct), 2))
            if worst_row else None
        ),
    )
    return await _store(key, model.model_dump(mode="json"))


@router.get("/by-strategy", response_model=list[StrategyBreakdown])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_by_strategy(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolved trades grouped by strategy_type, most-traded first."""
    key = _cache_key(user.id, "by_strategy")
    cached = await cache_get_json(key)
    if cached is not None:
        return cached

    rows = (
        await db.execute(
            select(
                JournalEntry.strategy_type,
                func.count().label("trade_count"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
                func.avg(JournalEntry.outcome_pnl_pct).label("avg_pnl"),
            )
            .where(*_resolved_filter(user.id))
            .group_by(JournalEntry.strategy_type)
            .order_by(func.count().desc())
        )
    ).all()

    payload = [
        StrategyBreakdown(
            strategy_type=row.strategy_type or "untagged",
            trade_count=row.trade_count,
            win_rate=_win_rate(int(row.wins or 0), row.trade_count),
            avg_pnl_pct=round(float(row.avg_pnl), 2) if row.avg_pnl is not None else 0.0,
        ).model_dump(mode="json")
        for row in rows
    ]
    return await _store(key, payload)


@router.get("/by-ticker", response_model=list[TickerBreakdown])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_by_ticker(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolved trades grouped by ticker, top 10 by trade count."""
    key = _cache_key(user.id, "by_ticker")
    cached = await cache_get_json(key)
    if cached is not None:
        return cached

    rows = (
        await db.execute(
            select(
                JournalEntry.ticker,
                func.count().label("trade_count"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
            )
            .where(*_resolved_filter(user.id))
            .group_by(JournalEntry.ticker)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()

    payload = [
        TickerBreakdown(
            ticker=row.ticker,
            trade_count=row.trade_count,
            win_rate=_win_rate(int(row.wins or 0), row.trade_count),
        ).model_dump(mode="json")
        for row in rows
    ]
    return await _store(key, payload)


@router.get("/equity-curve", response_model=list[EquityPoint])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_equity_curve(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cumulative P&L over time, from resolved trades ordered by resolved_at."""
    key = _cache_key(user.id, "equity_curve")
    cached = await cache_get_json(key)
    if cached is not None:
        return cached

    rows = (
        await db.execute(
            select(JournalEntry.resolved_at, JournalEntry.outcome_pnl_pct)
            .where(*_resolved_filter(user.id), JournalEntry.resolved_at.isnot(None))
            .order_by(JournalEntry.resolved_at.asc())
        )
    ).all()

    payload = []
    running = 0.0
    for row in rows:
        running += row.outcome_pnl_pct or 0.0
        payload.append(
            EquityPoint(
                date=row.resolved_at.date(), cumulative_pnl_pct=round(running, 2)
            ).model_dump(mode="json")
        )
    return await _store(key, payload)

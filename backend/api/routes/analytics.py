# Router for journal analytics endpoints — summary stats, per-strategy breakdown, equity curve.
from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from db.database import get_db
from db.models import JournalEntry, UserProfile

router = APIRouter(tags=["analytics"])

# A trade is "resolved" once it has a non-pending outcome.
RESOLVED_OUTCOMES = ("win", "loss", "scratch")


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


class EquityPoint(BaseModel):
    date: date
    cumulative_pnl_pct: float


# ---------------------------------------------------------------------------
# Helpers
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
        return AnalyticsSummaryResponse(
            total_trades=total_trades,
            resolved_trades=0,
            win_rate=0.0,
            avg_pnl_pct=0.0,
        )

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

    return AnalyticsSummaryResponse(
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


@router.get("/by-strategy", response_model=list[StrategyBreakdown])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_by_strategy(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolved trades grouped by strategy_type, most-traded first."""
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

    return [
        StrategyBreakdown(
            strategy_type=row.strategy_type or "untagged",
            trade_count=row.trade_count,
            win_rate=_win_rate(int(row.wins or 0), row.trade_count),
            avg_pnl_pct=round(float(row.avg_pnl), 2) if row.avg_pnl is not None else 0.0,
        )
        for row in rows
    ]


@router.get("/equity-curve", response_model=list[EquityPoint])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_equity_curve(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cumulative P&L over time, from resolved trades ordered by resolved_at."""
    rows = (
        await db.execute(
            select(JournalEntry.resolved_at, JournalEntry.outcome_pnl_pct)
            .where(*_resolved_filter(user.id), JournalEntry.resolved_at.isnot(None))
            .order_by(JournalEntry.resolved_at.asc())
        )
    ).all()

    curve: list[EquityPoint] = []
    running = 0.0
    for row in rows:
        running += row.outcome_pnl_pct or 0.0
        curve.append(EquityPoint(date=row.resolved_at.date(), cumulative_pnl_pct=round(running, 2)))
    return curve

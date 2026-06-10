# Router for trade journal endpoints — create, read, update, and delete journal entries.
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from api.schemas import (
    AISummaryResponse,
    CreateJournalEntryRequest,
    JournalEntryResponse,
    UpdateJournalNotesRequest,
    UpdateJournalOutcomeRequest,
)
from cache import cache_delete, cache_get_json, cache_set_json
from db.database import get_db
from db.models import AiSummary, JournalEntry, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["journal"])

ANALYTICS_CACHE_TTL = 3600


def _analytics_cache_key(user_id: uuid.UUID) -> str:
    return f"journal_analytics:{user_id}"


def _to_response(entry: JournalEntry, summary: AiSummary | None) -> JournalEntryResponse:
    response = JournalEntryResponse.model_validate(entry)
    if summary is not None:
        response.summary = AISummaryResponse.model_validate(summary)
    return response


async def _get_owned_entry(
    db: AsyncSession, entry_id: int, user: UserProfile
) -> JournalEntry:
    """Load a non-deleted entry owned by *user*, or raise 404."""
    entry = (
        await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == entry_id,
                JournalEntry.user_id == user.id,
                JournalEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


async def _summary_for(db: AsyncSession, entry: JournalEntry) -> AiSummary | None:
    if entry.ai_summary_id is None:
        return None
    return (
        await db.execute(select(AiSummary).where(AiSummary.id == entry.ai_summary_id))
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Analytics (must be registered before /{entry_id})
# ---------------------------------------------------------------------------

async def compute_journal_analytics(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    Aggregate journal performance for one user using SQL aggregation
    (never pulling all rows into Python).
    """
    resolved = (
        JournalEntry.user_id == user_id,
        JournalEntry.deleted_at.is_(None),
        JournalEntry.outcome != "pending",
        JournalEntry.outcome.isnot(None),
        JournalEntry.resolved_at.isnot(None),
    )

    total_entries = (
        await db.execute(
            select(func.count()).where(
                JournalEntry.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    overall_row = (
        await db.execute(
            select(
                func.count().label("resolved_count"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
                func.sum(case((JournalEntry.outcome == "loss", 1), else_=0)).label("losses"),
                func.sum(case((JournalEntry.outcome == "scratch", 1), else_=0)).label("scratches"),
                func.avg(
                    case(
                        (JournalEntry.outcome.in_(("win", "loss")), JournalEntry.outcome_pnl_pct),
                    )
                ).label("avg_pnl_pct"),
            ).where(*resolved)
        )
    ).one()

    resolved_count = overall_row.resolved_count or 0
    win_count = int(overall_row.wins or 0)

    overall_stats = {
        "total_entries": total_entries,
        "resolved_count": resolved_count,
        "win_count": win_count,
        "loss_count": int(overall_row.losses or 0),
        "scratch_count": int(overall_row.scratches or 0),
        "win_rate": round(win_count / resolved_count * 100, 1) if resolved_count else 0.0,
        "avg_pnl_pct": (
            round(float(overall_row.avg_pnl_pct), 2)
            if overall_row.avg_pnl_pct is not None else None
        ),
    }

    strategy_rows = (
        await db.execute(
            select(
                JournalEntry.strategy_type,
                func.count().label("trade_count"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
                func.avg(
                    case(
                        (JournalEntry.outcome.in_(("win", "loss")), JournalEntry.outcome_pnl_pct),
                    )
                ).label("avg_pnl_pct"),
            )
            .where(*resolved)
            .group_by(JournalEntry.strategy_type)
        )
    ).all()

    by_strategy = [
        {
            "strategy_type": row.strategy_type or "untagged",
            "trade_count": row.trade_count,
            "win_rate": round(int(row.wins or 0) / row.trade_count * 100, 1),
            "avg_pnl_pct": (
                round(float(row.avg_pnl_pct), 2) if row.avg_pnl_pct is not None else None
            ),
        }
        for row in strategy_rows
    ]

    ticker_rows = (
        await db.execute(
            select(
                JournalEntry.ticker,
                func.count().label("trade_count"),
                func.sum(case((JournalEntry.outcome == "win", 1), else_=0)).label("wins"),
            )
            .where(*resolved)
            .group_by(JournalEntry.ticker)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()

    by_ticker = [
        {
            "ticker": row.ticker,
            "trade_count": row.trade_count,
            "win_rate": round(int(row.wins or 0) / row.trade_count * 100, 1),
        }
        for row in ticker_rows
    ]

    trend_rows = (
        await db.execute(
            select(
                JournalEntry.resolved_at,
                JournalEntry.outcome,
                JournalEntry.outcome_pnl_pct,
            )
            .where(*resolved)
            .order_by(JournalEntry.resolved_at.desc())
            .limit(30)
        )
    ).all()

    recent_trend = [
        {
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "outcome": row.outcome,
            "outcome_pnl_pct": row.outcome_pnl_pct,
        }
        for row in reversed(trend_rows)
    ]

    return {
        "overall_stats": overall_stats,
        "by_strategy": by_strategy,
        "by_ticker": by_ticker,
        "recent_trend": recent_trend,
    }


@router.get("/analytics")
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_journal_analytics(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated performance data for the current user (cached hourly)."""
    cache_key = _analytics_cache_key(user.id)
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    analytics = await compute_journal_analytics(user.id, db)
    await cache_set_json(cache_key, analytics, ttl_seconds=ANALYTICS_CACHE_TTL)
    return analytics


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=JournalEntryResponse, status_code=201)
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def create_journal_entry(
    request: Request,
    body: CreateJournalEntryRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = None
    if body.ai_summary_id is not None:
        summary = (
            await db.execute(select(AiSummary).where(AiSummary.id == body.ai_summary_id))
        ).scalar_one_or_none()
        if summary is None:
            raise HTTPException(
                status_code=404, detail=f"AI summary {body.ai_summary_id} not found"
            )

    entry = JournalEntry(
        user_id=user.id,
        ticker=body.ticker,
        ai_summary_id=body.ai_summary_id,
        user_notes=body.user_notes,
        entry_price=body.entry_price,
        strategy_type=body.strategy_type,
        expiry_date=body.expiry_date,
        outcome="pending",
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)

    return _to_response(entry, summary)


@router.get("", response_model=list[JournalEntryResponse])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def list_journal_entries(
    request: Request,
    outcome: str | None = Query(default=None, pattern="^(win|loss|scratch|pending)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(JournalEntry)
        .where(JournalEntry.user_id == user.id, JournalEntry.deleted_at.is_(None))
        .order_by(JournalEntry.saved_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if outcome is not None:
        query = query.where(JournalEntry.outcome == outcome)

    entries = (await db.execute(query)).scalars().all()
    return [_to_response(e, await _summary_for(db, e)) for e in entries]


@router.get("/{entry_id}", response_model=JournalEntryResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_journal_entry(
    request: Request,
    entry_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(db, entry_id, user)
    return _to_response(entry, await _summary_for(db, entry))


@router.patch("/{entry_id}/outcome", response_model=JournalEntryResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def update_journal_outcome(
    request: Request,
    entry_id: int,
    body: UpdateJournalOutcomeRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(db, entry_id, user)

    entry.outcome = body.outcome
    entry.outcome_pnl_pct = body.outcome_pnl_pct
    entry.resolved_at = (
        datetime.now(tz=timezone.utc) if body.outcome != "pending" else None
    )
    await db.flush()
    await db.refresh(entry)

    # Outcomes feed the analytics aggregates — invalidate the hourly cache
    await cache_delete(_analytics_cache_key(user.id))

    return _to_response(entry, await _summary_for(db, entry))


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def update_journal_notes(
    request: Request,
    entry_id: int,
    body: UpdateJournalNotesRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(db, entry_id, user)
    entry.user_notes = body.user_notes
    await db.flush()
    await db.refresh(entry)
    return _to_response(entry, await _summary_for(db, entry))


@router.delete("/{entry_id}", status_code=204)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def delete_journal_entry(
    request: Request,
    entry_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(db, entry_id, user)
    entry.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return Response(status_code=204)

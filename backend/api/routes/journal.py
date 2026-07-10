# Router for trade journal endpoints — create, read, update, and delete journal entries.
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from api.routes.analytics import invalidate_analytics_cache
from api.schemas import (
    AISummaryResponse,
    CreateJournalEntryRequest,
    JournalEntryResponse,
    UpdateJournalEntryRequest,
)
from db.database import get_db
from db.models import AiSummary, JournalEntry, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["journal"])

# Fields whose change invalidates the cached analytics aggregates.
_ANALYTICS_FIELDS = {"outcome", "outcome_pnl_pct", "strategy_type"}


def _to_response(entry: JournalEntry, summary: AiSummary | None) -> JournalEntryResponse:
    response = JournalEntryResponse.model_validate(entry)
    if summary is not None:
        response.summary = AISummaryResponse.model_validate(summary)
    return response


async def _get_owned_entry(
    db: AsyncSession, entry_id: int, user: UserProfile
) -> JournalEntry:
    """Load a non-deleted entry owned by *user*, or raise 404 if not found."""
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


async def _get_entry_for_write(
    db: AsyncSession, entry_id: int, user: UserProfile
) -> JournalEntry:
    """Load a non-deleted entry for mutation, or raise 404.

    A row that exists but belongs to another user is reported as 404 with the
    same detail as a missing row, so a caller cannot enumerate which entry ids
    exist. Ownership is still checked explicitly here rather than filtered in
    SQL, so this enforcement stays directly testable.
    """
    entry = (
        await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == entry_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


async def _summary_for(db: AsyncSession, entry: JournalEntry) -> AiSummary | None:
    if entry.ai_summary_id is None:
        return None
    return (
        await db.execute(select(AiSummary).where(AiSummary.id == entry.ai_summary_id))
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=JournalEntryResponse, status_code=201)
@limiter.limit("30/minute", key_func=user_or_ip_key)
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


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def update_journal_entry(
    request: Request,
    entry_id: int,
    body: UpdateJournalEntryRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partially update a journal entry the current user owns (404 if not).

    Only the fields present in the request are changed. When ``outcome`` moves
    off ``pending``, ``resolved_at`` is stamped with the current time; moving
    back to ``pending`` clears it.
    """
    entry = await _get_entry_for_write(db, entry_id, user)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)

    if "outcome" in updates:
        entry.resolved_at = (
            datetime.now(tz=timezone.utc) if updates["outcome"] != "pending" else None
        )

    await db.flush()
    await db.refresh(entry)

    # Outcome / P&L / strategy changes feed analytics — bust the cached aggregates.
    if _ANALYTICS_FIELDS & updates.keys():
        await invalidate_analytics_cache(user.id)

    return _to_response(entry, await _summary_for(db, entry))


@router.delete("/{entry_id}", status_code=204)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def delete_journal_entry(
    request: Request,
    entry_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an entry the current user owns (404 if not) by stamping deleted_at."""
    entry = await _get_entry_for_write(db, entry_id, user)
    entry.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return Response(status_code=204)

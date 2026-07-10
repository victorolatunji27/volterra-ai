# Pydantic request/response models for every API endpoint.
import re
from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from strategies import STRATEGY_TAG_SET

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")

ALLOWED_OUTCOMES = {"win", "loss", "scratch", "pending"}

# Shared taxonomy — see strategies.py (single source of truth).
ALLOWED_STRATEGY_TAGS = STRATEGY_TAG_SET

# Literal forms for request bodies: invalid values 422 at the model boundary.
# Keep in sync with strategies.STRATEGY_TAGS.
StrategyTag = Literal[
    "momentum", "earnings_play", "iv_crush", "breakout", "hedge", "contrarian", "neutral",
]
Outcome = Literal["win", "loss", "scratch", "pending"]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AISummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setup_summary: Optional[str] = None
    flow_interpretation: Optional[str] = None
    risk_note: Optional[str] = None
    strategy_tags: Optional[list[str]] = None
    created_at: datetime


class FlowScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    scan_date: date
    call_volume: Optional[int] = None
    put_volume: Optional[int] = None
    oi_ratio: Optional[float] = None
    call_put_ratio: Optional[float] = None
    avg_strike: Optional[float] = None
    avg_expiry: Optional[date] = None
    iv_rank: Optional[float] = None
    price_at_scan: Optional[float] = None
    created_at: datetime
    summary: Optional[AISummaryResponse] = None


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    user_notes: Optional[str] = None
    entry_price: Optional[float] = None
    strategy_type: Optional[str] = None
    expiry_date: Optional[date] = None
    outcome: Optional[str] = None
    outcome_pnl_pct: Optional[float] = None
    saved_at: datetime
    resolved_at: Optional[datetime] = None
    summary: Optional[AISummaryResponse] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    tier: str
    strategy_tags: Optional[list[str]] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateJournalEntryRequest(BaseModel):
    # extra="forbid": unknown body keys 422 instead of being silently dropped.
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z]{1,10}$")
    ai_summary_id: Optional[int] = Field(None, ge=1)
    entry_price: Optional[float] = Field(None, gt=0, lt=1_000_000)
    outcome_pnl_pct: Optional[float] = Field(None, ge=-100, le=10_000)
    strategy_type: Optional[StrategyTag] = None
    expiry_date: Optional[date] = None
    user_notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v: object) -> object:
        # Normalise before the pattern check so "aapl " is accepted as "AAPL".
        return v.strip().upper() if isinstance(v, str) else v


class UpdateJournalEntryRequest(BaseModel):
    """Partial update — every field optional; only provided keys are applied.

    Use exclude_unset when consuming so an omitted field is left unchanged
    while an explicit null clears it.
    """
    model_config = ConfigDict(extra="forbid")

    user_notes: Optional[str] = Field(None, max_length=2000)
    entry_price: Optional[float] = Field(None, gt=0, lt=1_000_000)
    strategy_type: Optional[StrategyTag] = None
    expiry_date: Optional[date] = None
    outcome: Optional[Outcome] = None
    outcome_pnl_pct: Optional[float] = Field(None, ge=-100, le=10_000)


class UpdateStrategyTagsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_tags: list[StrategyTag] = Field(max_length=7)

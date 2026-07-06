# Pydantic request/response models for every API endpoint.
import re
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from strategies import STRATEGY_TAG_SET

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")

ALLOWED_OUTCOMES = {"win", "loss", "scratch", "pending"}

# Shared taxonomy — see strategies.py (single source of truth).
ALLOWED_STRATEGY_TAGS = STRATEGY_TAG_SET


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
    ticker: str
    ai_summary_id: Optional[int] = None
    user_notes: Optional[str] = None
    entry_price: Optional[float] = None
    strategy_type: Optional[str] = None
    expiry_date: Optional[date] = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not TICKER_PATTERN.match(v):
            raise ValueError("ticker must be 1-5 uppercase letters (A-Z)")
        return v

    @field_validator("user_notes")
    @classmethod
    def validate_user_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 2000:
            raise ValueError("user_notes must be at most 2000 characters")
        return v

    @field_validator("entry_price")
    @classmethod
    def validate_entry_price(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.01 <= v <= 1_000_000):
            raise ValueError("entry_price must be between 0.01 and 1000000")
        return v

    @field_validator("strategy_type")
    @classmethod
    def validate_strategy_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_STRATEGY_TAGS:
            raise ValueError(
                f"strategy_type must be one of: {', '.join(sorted(ALLOWED_STRATEGY_TAGS))}"
            )
        return v


class UpdateJournalEntryRequest(BaseModel):
    """Partial update — every field optional; only provided keys are applied.

    Use exclude_unset when consuming so an omitted field is left unchanged
    while an explicit null clears it.
    """
    user_notes: Optional[str] = None
    entry_price: Optional[float] = None
    strategy_type: Optional[str] = None
    expiry_date: Optional[date] = None
    outcome: Optional[str] = None
    outcome_pnl_pct: Optional[float] = None

    @field_validator("user_notes")
    @classmethod
    def validate_user_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 2000:
            raise ValueError("user_notes must be at most 2000 characters")
        return v

    @field_validator("entry_price")
    @classmethod
    def validate_entry_price(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.01 <= v <= 1_000_000):
            raise ValueError("entry_price must be between 0.01 and 1000000")
        return v

    @field_validator("strategy_type")
    @classmethod
    def validate_strategy_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_STRATEGY_TAGS:
            raise ValueError(
                f"strategy_type must be one of: {', '.join(sorted(ALLOWED_STRATEGY_TAGS))}"
            )
        return v

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_OUTCOMES:
            raise ValueError(
                f"outcome must be one of: {', '.join(sorted(ALLOWED_OUTCOMES))}"
            )
        return v


class UpdateStrategyTagsRequest(BaseModel):
    strategy_tags: list[str]

    @field_validator("strategy_tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        invalid = [tag for tag in v if tag not in ALLOWED_STRATEGY_TAGS]
        if invalid:
            raise ValueError(
                f"invalid strategy tags: {invalid}. "
                f"Allowed: {', '.join(sorted(ALLOWED_STRATEGY_TAGS))}"
            )
        return v

# SQLAlchemy ORM models — User, ScanResult, JournalEntry, and related tables.
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    strategy_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        back_populates="user", foreign_keys="JournalEntry.user_id"
    )


class FlowScan(Base):
    __tablename__ = "flow_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    scan_date: Mapped[date] = mapped_column(Date, nullable=False)
    call_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    put_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    oi_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_strike: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    iv_rank: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_at_scan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ai_summaries: Mapped[list["AiSummary"]] = relationship(back_populates="flow_scan")


class AiSummary(Base):
    __tablename__ = "ai_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flow_scans.id"), nullable=False
    )
    setup_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flow_interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    news_used: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    flow_scan: Mapped["FlowScan"] = relationship(back_populates="ai_summaries")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="ai_summary")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    ai_summary_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ai_summaries.id"), nullable=True
    )
    user_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strategy_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outcome_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Not a FK — user_id is a Supabase auth UUID resolved at the application layer
    user: Mapped["UserProfile"] = relationship(
        back_populates="journal_entries",
        primaryjoin="JournalEntry.user_id == foreign(UserProfile.id)",
        viewonly=True,
    )
    ai_summary: Mapped[Optional["AiSummary"]] = relationship(back_populates="journal_entries")


class DigestLog(Base):
    __tablename__ = "digest_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    recipient_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tickers_included: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

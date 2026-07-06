# Router for the ticker detail page — latest scan, AI summary, news, history, and price chart.
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from api.schemas import TICKER_PATTERN, AISummaryResponse, FlowScanResponse
from data.market_data import get_price_history
from db.database import get_db
from db.models import AiSummary, FlowScan, UserProfile

router = APIRouter(tags=["ticker"])

HISTORY_LIMIT = 10
PRICE_SERIES_DAYS = 30


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TickerHistoryPoint(BaseModel):
    scan_date: date
    oi_ratio: float | None = None
    call_put_ratio: float | None = None
    iv_rank: float | None = None
    price_at_scan: float | None = None


class PricePoint(BaseModel):
    date: date
    close: float


class TickerDetailResponse(BaseModel):
    symbol: str
    latest: FlowScanResponse
    news: Any | None = None
    history: list[TickerHistoryPoint]
    price_series: list[PricePoint] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not TICKER_PATTERN.match(symbol):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    return symbol


def _history_point(scan: FlowScan) -> TickerHistoryPoint:
    return TickerHistoryPoint(
        scan_date=scan.scan_date,
        oi_ratio=scan.oi_ratio,
        # call_put_ratio is not a column — it lives in the stored raw_data payload
        call_put_ratio=(scan.raw_data or {}).get("call_put_ratio"),
        iv_rank=scan.iv_rank,
        price_at_scan=scan.price_at_scan,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("/{symbol}", response_model=TickerDetailResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_ticker_detail(
    request: Request,
    symbol: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything the ticker detail page needs for one symbol."""
    symbol = _validate_symbol(symbol)

    # Most recent scan for this ticker (drives the 404 for unknown symbols).
    latest_scan = (
        await db.execute(
            select(FlowScan)
            .where(FlowScan.ticker == symbol)
            .order_by(FlowScan.scan_date.desc(), FlowScan.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_scan is None:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    # Most recent AI summary attached to that scan.
    summary = (
        await db.execute(
            select(AiSummary)
            .where(AiSummary.flow_scan_id == latest_scan.id)
            .order_by(AiSummary.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Last 10 scans, returned oldest → newest for the history timeline.
    recent_scans = (
        await db.execute(
            select(FlowScan)
            .where(FlowScan.ticker == symbol)
            .order_by(FlowScan.scan_date.desc(), FlowScan.id.desc())
            .limit(HISTORY_LIMIT)
        )
    ).scalars().all()
    history = [_history_point(scan) for scan in reversed(recent_scans)]

    # Price chart — a yfinance failure degrades to price_series=None, never a 5xx.
    price_series = await get_price_history(symbol, days=PRICE_SERIES_DAYS)

    latest = FlowScanResponse.model_validate(latest_scan)
    latest.call_put_ratio = (latest_scan.raw_data or {}).get("call_put_ratio")
    if summary is not None:
        latest.summary = AISummaryResponse.model_validate(summary)

    return TickerDetailResponse(
        symbol=symbol,
        latest=latest,
        news=summary.news_used if summary is not None else None,
        history=history,
        price_series=price_series,
    )

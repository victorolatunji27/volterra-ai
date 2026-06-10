# Router for options scan endpoints — trigger, list, and retrieve daily scan results.
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.limiter import limiter
from api.schemas import TICKER_PATTERN, AISummaryResponse, FlowScanResponse
from db.database import get_db
from db.models import AiSummary, FlowScan

router = APIRouter(tags=["scans"])


def _validate_ticker(ticker: str) -> str:
    """Normalise and validate a ticker path parameter, raising 400 if bad."""
    ticker = ticker.strip().upper()
    if not TICKER_PATTERN.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    return ticker


async def _latest_summary(db: AsyncSession, flow_scan_id: int) -> AiSummary | None:
    """Return the most recent ai_summaries row for one flow scan."""
    return (
        await db.execute(
            select(AiSummary)
            .where(AiSummary.flow_scan_id == flow_scan_id)
            .order_by(AiSummary.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _to_response(scan: FlowScan, summary: AiSummary | None) -> FlowScanResponse:
    """Build a FlowScanResponse, pulling call_put_ratio out of raw_data."""
    response = FlowScanResponse.model_validate(scan)
    response.call_put_ratio = (scan.raw_data or {}).get("call_put_ratio")
    if summary is not None:
        response.summary = AISummaryResponse.model_validate(summary)
    return response


@router.get("/today", response_model=list[FlowScanResponse])
@limiter.limit("60/minute")
async def get_todays_scans(request: Request, db: AsyncSession = Depends(get_db)):
    """Today's top 10 flow scans, each with its AI summary joined in."""
    scans = (
        await db.execute(
            select(FlowScan)
            .where(FlowScan.scan_date == date.today())
            .order_by(FlowScan.oi_ratio.desc())
            .limit(10)
        )
    ).scalars().all()

    return [_to_response(scan, await _latest_summary(db, scan.id)) for scan in scans]


@router.get("/{ticker}", response_model=list[FlowScanResponse])
@limiter.limit("60/minute")
async def get_ticker_scans(
    request: Request,
    ticker: str,
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """The last N days of scans for one ticker, most recent first."""
    ticker = _validate_ticker(ticker)
    since = date.today() - timedelta(days=days)

    scans = (
        await db.execute(
            select(FlowScan)
            .where(FlowScan.ticker == ticker, FlowScan.scan_date >= since)
            .order_by(FlowScan.scan_date.desc())
        )
    ).scalars().all()

    return [_to_response(scan, await _latest_summary(db, scan.id)) for scan in scans]


@router.get("/{ticker}/summary", response_model=AISummaryResponse)
@limiter.limit("60/minute")
async def get_ticker_summary(
    request: Request,
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """The most recent AI summary for one ticker."""
    ticker = _validate_ticker(ticker)

    summary = (
        await db.execute(
            select(AiSummary)
            .join(FlowScan, AiSummary.flow_scan_id == FlowScan.id)
            .where(FlowScan.ticker == ticker)
            .order_by(AiSummary.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if summary is None:
        raise HTTPException(status_code=404, detail=f"No summary found for {ticker}")

    return summary

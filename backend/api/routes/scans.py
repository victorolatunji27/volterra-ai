# Router for options scan endpoints — trigger, list, and retrieve daily scan results.
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from api.schemas import TICKER_PATTERN, AISummaryResponse, FlowScanResponse
from db.database import get_db
from db.models import AiSummary, FlowScan, UserProfile

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


@router.post("/trigger")
@limiter.limit("3/hour", key_func=user_or_ip_key)
async def trigger_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfile = Depends(get_current_user),
):
    """Kick off a full scan immediately (authenticated, 3/hour per user).

    The scan takes minutes (30 tickers + AI summaries), so it runs as a
    background task and this returns as soon as it is scheduled.
    """
    # Lazy import: keeps the heavy scan pipeline (yfinance/pandas) out of the
    # router's import path and makes the task easy to patch in tests.
    from scheduler.daily_scan import run_daily_scan

    background_tasks.add_task(run_daily_scan)
    return {"status": "started"}


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


# ---------------------------------------------------------------------------
# Public demo setup — registered separately in main.py at /api/demo.
# No auth, no database, no Claude: a hardcoded illustrative scan card for the
# landing page, in the exact shape the frontend renders without branching.
# ---------------------------------------------------------------------------

demo_router = APIRouter(tags=["demo"])


class DemoSetupResponse(BaseModel):
    is_demo: bool
    ticker: str
    company_name: str
    strategy_tag: str
    call_put_ratio: float
    oi_ratio: float
    iv_rank: int
    price_at_scan: float
    price_change_pct: float
    avg_strike: float
    expiry: str
    setup_summary: str
    flow_interpretation: str
    risk_note: str


def _next_june_21() -> str:
    """The next occurrence of June 21 (ISO date).

    The demo card's copy references a 'Jun 21' expiry, so the date stays
    hardcoded to that day — but rolls forward each year so the illustrative
    setup never looks expired.
    """
    today = date.today()
    year = today.year if today <= date(today.year, 6, 21) else today.year + 1
    return date(year, 6, 21).isoformat()


# Built once at import; every request returns this constant with only the
# expiry recomputed.
_DEMO_SETUP = DemoSetupResponse(
    is_demo=True,
    ticker="NVDA",
    company_name="NVIDIA Corp.",
    strategy_tag="momentum",
    call_put_ratio=2.8,
    oi_ratio=4.1,
    iv_rank=61,
    price_at_scan=172.40,
    price_change_pct=2.4,
    avg_strike=180.0,
    expiry="2025-06-21",  # placeholder — replaced per request by _next_june_21()
    setup_summary=(
        "Heavy call buying concentrated in near-dated $180 strikes ahead of the "
        "GTC keynote. Volume is running 4x open interest, suggesting fresh "
        "positioning rather than rolls."
    ),
    flow_interpretation=(
        "The dominant signal is fresh call buying in the $180 strike expiring Jun 21."
    ),
    risk_note=(
        "IV is elevated — a post-event vol crush could erase gains even if the "
        "stock moves up."
    ),
)


@demo_router.get("/setup", response_model=DemoSetupResponse)
@limiter.limit("60/minute")
async def demo_setup(request: Request):
    """Static illustrative setup for the landing page. Public — no auth, no DB."""
    return _DEMO_SETUP.model_copy(update={"expiry": _next_june_21()})

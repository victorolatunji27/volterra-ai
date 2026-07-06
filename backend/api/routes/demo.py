# Public demo endpoint — a static, illustrative flow setup for the landing page.
#
# Deliberately touches nothing: no auth, no database, no Claude call. The
# response is a hardcoded constant built once at import, so the logged-out
# landing page's "View demo setup" button stays instant.
from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.limiter import limiter

router = APIRouter(tags=["demo"])


class DemoSetupResponse(BaseModel):
    ticker: str
    strategy_tags: list[str]
    call_put_ratio: float
    oi_ratio: float
    iv_rank: float
    price_at_scan: float
    setup_summary: str
    risk_note: str
    is_demo: bool = True


# Built once. "DEMO" is not a real symbol, and the copy says so — this can
# never be mistaken for a live scan.
_DEMO_SETUP = DemoSetupResponse(
    ticker="DEMO",
    strategy_tags=["momentum"],
    call_put_ratio=5.6,
    oi_ratio=4.2,
    iv_rank=68.0,
    price_at_scan=498.00,
    setup_summary=(
        "Sample setup — not live data. This illustrative card shows heavily "
        "skewed call buying with a 5.6 call/put ratio and volume running 4.2x "
        "the open-interest baseline. The flow clusters above the current price, "
        "consistent with directional bullish positioning. IV rank near 68 means "
        "options are moderately expensive relative to the past year."
    ),
    risk_note=(
        "Example risk note. Elevated IV makes long premium expensive, and a "
        "setup like this fails if the move does not develop before expiry. "
        "Not financial advice."
    ),
    is_demo=True,
)


@router.get("/setup", response_model=DemoSetupResponse)
@limiter.limit("60/minute")
async def demo_setup(request: Request):
    """Return the static demo flow setup. Public — no auth, no DB, no Claude."""
    return _DEMO_SETUP

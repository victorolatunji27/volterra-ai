# Router for user management endpoints — registration, authentication, and profile updates.
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from api.schemas import UpdateStrategyTagsRequest, UserProfileResponse
from db.database import get_db
from db.models import UserProfile
from mailer.digest import send_digest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])

TEST_ALERT_HTML = (
    '<table width="600" cellpadding="0" cellspacing="0" border="0" '
    'style="max-width: 600px; background-color: #ffffff;">'
    '<tr><td style="font-family: Arial, sans-serif; font-size: 16px; color: #111827; '
    'padding: 16px 0;">This is a test of your VolterraAI strategy alerts.</td></tr>'
    "</table>"
)


@router.get("/me", response_model=UserProfileResponse)
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def get_me(request: Request, user: UserProfile = Depends(get_current_user)):
    return user


@router.patch("/me/strategies", response_model=list[str])
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def update_my_strategies(
    request: Request,
    body: UpdateStrategyTagsRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overwrite the current user's strategy tags and return the updated list.

    Tags are validated against the shared allowed set by UpdateStrategyTagsRequest.
    """
    user.strategy_tags = body.strategy_tags
    await db.flush()
    await db.refresh(user)
    return user.strategy_tags


@router.post("/me/test-alert")
@limiter.limit("3/day", key_func=user_or_ip_key)
async def send_test_alert(
    request: Request,
    user: UserProfile = Depends(get_current_user),
):
    if user.tier != "pro":
        raise HTTPException(status_code=403, detail="Strategy alerts are a Pro feature")

    sent = send_digest([user.email], TEST_ALERT_HTML, "VolterraAI test alert")
    if not sent:
        raise HTTPException(status_code=502, detail="Failed to send test alert email")

    return {"sent": True}

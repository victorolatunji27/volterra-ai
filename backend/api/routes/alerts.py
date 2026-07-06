# Router for strategy alert history — the current user's recorded alert_log rows.
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.limiter import limiter, user_or_ip_key
from db.database import get_db
from db.models import AlertLog, UserProfile

router = APIRouter(tags=["alerts"])


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tickers: list[str] | None = None
    sent_at: datetime


@router.get("", response_model=list[AlertResponse])
@limiter.limit("30/minute", key_func=user_or_ip_key)
async def list_alerts(
    request: Request,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The current user's strategy alert history, newest first."""
    rows = (
        await db.execute(
            select(AlertLog)
            .where(AlertLog.user_id == user.id)
            .order_by(AlertLog.sent_at.desc())
        )
    ).scalars().all()
    return rows

# Shared FastAPI dependencies — database sessions, current-user injection, rate-limit guards.
import logging
import os
import uuid

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import UserProfile

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

_CREDENTIALS_ERROR = HTTPException(status_code=401, detail="Invalid or expired token")


def decode_token(token: str) -> dict:
    """
    Verify and decode a Supabase JWT. Raises jwt exceptions on failure.

    Supabase signs access tokens with HS256 and sets aud="authenticated".
    """
    return jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
    )


def extract_user_id_from_request(request: Request) -> str | None:
    """
    Best-effort user-id extraction for rate-limit keying.
    Returns the "sub" claim, or None when no valid bearer token is present.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth_header.removeprefix("Bearer ").strip())
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """
    Resolve the authenticated user from the Authorization: Bearer header.

    Verifies the Supabase JWT signature, extracts the "sub" UUID, and loads
    the matching user_profiles row. Raises 401 on any failure.
    """
    if not SUPABASE_JWT_SECRET:
        logger.error("get_current_user: SUPABASE_JWT_SECRET is not configured.")
        raise _CREDENTIALS_ERROR

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _CREDENTIALS_ERROR

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise _CREDENTIALS_ERROR

    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        logger.info("get_current_user: JWT validation failed — %s", exc)
        raise _CREDENTIALS_ERROR from exc

    sub = payload.get("sub")
    try:
        user_id = uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        logger.info("get_current_user: invalid sub claim %r", sub)
        raise _CREDENTIALS_ERROR from exc

    user = (
        await db.execute(select(UserProfile).where(UserProfile.id == user_id))
    ).scalar_one_or_none()

    if user is None:
        logger.info("get_current_user: no user_profiles row for %s", user_id)
        raise _CREDENTIALS_ERROR

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserProfile | None:
    """Like get_current_user, but returns None instead of raising 401."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None

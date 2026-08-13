# Shared FastAPI dependencies — database sessions, current-user injection, rate-limit guards.
import logging
import os
import uuid

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import UserProfile

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

_CREDENTIALS_ERROR = HTTPException(status_code=401, detail="Invalid or expired token")

# Lazily built so importing this module never makes a network call; the
# client caches fetched keys itself (lifespan bounds how long a rotated
# Supabase signing key takes to be picked up without a restart).
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", lifespan=3600
        )
    return _jwks_client


def decode_token(token: str) -> dict:
    """
    Verify and decode a Supabase JWT. Raises jwt exceptions on failure.

    Newer Supabase projects sign access tokens with an asymmetric key
    (typically ES256) published at /auth/v1/.well-known/jwks.json — that is
    the primary path here, selected by SUPABASE_URL being set. Projects still
    on the legacy shared HS256 secret are supported as a fallback via
    SUPABASE_JWT_SECRET, so this works regardless of which signing mode a
    given project uses without needing to hardcode the assumption.
    """
    if SUPABASE_URL:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
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
    the matching user_profiles row — creating it on first sight if the
    Supabase trigger (migration 003) never ran for this user. Raises 401 on
    any failure.
    """
    if not SUPABASE_URL and not SUPABASE_JWT_SECRET:
        logger.error(
            "get_current_user: neither SUPABASE_URL (JWKS) nor SUPABASE_JWT_SECRET is configured."
        )
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
        # The token is valid, so this is a real Supabase user without a
        # profile row — self-heal rather than 401-looping them out of the app.
        user = await _create_profile(db, user_id, payload)

    return user


async def _create_profile(db: AsyncSession, user_id: uuid.UUID, payload: dict) -> UserProfile:
    """Create the user_profiles row for an authenticated Supabase user.

    Normally migration 003's trigger has already done this at signup; this
    covers users created before the trigger existed, a trigger that failed,
    and accounts added straight from the Supabase dashboard.
    """
    email = payload.get("email") or ""
    if not email:
        # Phone-only / anonymous signups have no email claim. The row is still
        # created (email is NOT NULL but may be empty); they simply receive no
        # digest or alert mail until an address is set.
        logger.warning("_create_profile: no email claim for %s — creating with empty email.", user_id)

    profile = UserProfile(id=user_id, email=email, tier="free")
    db.add(profile)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent request won the race — reuse the row it created.
        await db.rollback()
        existing = (
            await db.execute(select(UserProfile).where(UserProfile.id == user_id))
        ).scalar_one_or_none()
        if existing is None:
            logger.error("_create_profile: insert conflicted but no row found for %s", user_id)
            raise _CREDENTIALS_ERROR
        return existing

    # Pull server defaults (created_at) so response models validate.
    await db.refresh(profile)
    logger.info("_create_profile: created user_profiles row for %s", user_id)
    return profile


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserProfile | None:
    """Like get_current_user, but returns None instead of raising 401."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None

# Async Redis cache helper backed by the Upstash REST API.
#
# The .env provides UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN, which
# speak HTTP — not the Redis wire protocol — so we use httpx instead of
# redis-py. Every function degrades gracefully: if the cache is unreachable
# or unconfigured, callers simply see a cache miss and proceed without it.
import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

UPSTASH_URL: str = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

_HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
_TIMEOUT = 5.0


def cache_configured() -> bool:
    """Return True when Upstash credentials are present in the environment."""
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


async def cache_get_json(key: str) -> Any | None:
    """
    Fetch *key* from Upstash and JSON-decode the stored value.

    Returns the decoded object, or None on a miss, decode failure,
    or any transport error.
    """
    if not cache_configured():
        return None

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            response = await client.get(f"{UPSTASH_URL}/get/{key}")
            response.raise_for_status()
            raw = response.json().get("result")
    except Exception as exc:
        logger.warning("cache_get_json(%s): cache unavailable — %s", key, exc)
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("cache_get_json(%s): stored value is not valid JSON.", key)
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> bool:
    """
    JSON-encode *value* and store it under *key* with an expiry of
    *ttl_seconds*. Returns True on success, False otherwise.
    """
    if not cache_configured():
        return False

    try:
        payload = json.dumps(value)
    except (TypeError, ValueError) as exc:
        logger.warning("cache_set_json(%s): value not JSON-serialisable — %s", key, exc)
        return False

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{UPSTASH_URL}/set/{key}",
                params={"EX": ttl_seconds},
                content=payload,
            )
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("cache_set_json(%s): cache write failed — %s", key, exc)
        return False


async def cache_delete(key: str) -> bool:
    """Delete *key* from the cache. Returns True on success."""
    if not cache_configured():
        return False

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            response = await client.get(f"{UPSTASH_URL}/del/{key}")
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("cache_delete(%s): cache delete failed — %s", key, exc)
        return False

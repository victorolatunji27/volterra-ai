# slowapi rate limiter shared by main.py and the route modules.
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.deps import extract_user_id_from_request


def user_or_ip_key(request: Request) -> str:
    """
    Rate-limit key: the JWT user id when a valid bearer token is present,
    falling back to the client IP for anonymous requests.
    """
    user_id = extract_user_id_from_request(request)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


# Default limit applies to every route that has no explicit decorator.
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

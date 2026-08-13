# Entry point for the Volterra AI FastAPI application; wires up routers and app lifecycle events.
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.limiter import limiter
from api.routes.alerts import router as alerts_router
from api.routes.analytics import router as analytics_router
from api.routes.journal import router as journal_router
from api.routes.scans import demo_router
from api.routes.scans import router as scans_router
from api.routes.ticker import router as ticker_router
from api.routes.users import router as users_router
from db.database import engine

load_dotenv()

logger = logging.getLogger(__name__)

# ── Required-config check: fail at startup, not with a confusing runtime
#    error deep in a request. Hard-crash only in production — local dev, the
#    test suite, and CI all run intentionally degraded (no Resend/Upstash),
#    so there they get a loud warning instead.
REQUIRED_ENV_VARS = [
    "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME",
    "ANTHROPIC_API_KEY", "NEWSAPI_KEY", "RESEND_API_KEY",
    "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
    # Production runs on Tradier; without a key the scan would silently fall
    # back to yfinance, which gets rate-limited from cloud IPs.
    "TRADIER_API_KEY",
]
_missing_env = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if _missing_env:
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise RuntimeError(f"Missing required env vars: {_missing_env}")
    logger.warning(
        "Missing env vars (features degraded; fatal in production): %s",
        _missing_env,
    )

# ── Sentry (skip silently in local dev when SENTRY_DSN is unset) ────────────
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        profiles_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "development"),
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: the engine's pool is created lazily; start the scheduler unless
    # disabled (set ENABLE_SCHEDULER=false for local API work or test runs).
    scheduler = None
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
        try:
            from scheduler.daily_scan import initialize_scheduler
            scheduler = initialize_scheduler()
        except Exception:
            logger.exception("lifespan: scheduler failed to start — continuing without it.")
    yield
    # Shutdown: stop jobs first, then close the connection pool.
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="VolterraAI API",
    description="AI-powered options flow analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Rate limiting ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    # Same JSON shape as FastAPI's other errors ({"detail": ...}).
    retry_after = int(exc.headers.get("Retry-After", 60)) if exc.headers else 60
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded. Try again in {retry_after}s."},
        headers={"Retry-After": str(retry_after)},
    )


# ── Global exception handler — never leak stack traces to clients ───────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    # A custom handler swallows the exception before Sentry's ASGI integration
    # sees it, so capture explicitly. No-op when Sentry isn't initialized.
    sentry_sdk.capture_exception(exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── CORS ─────────────────────────────────────────────────────────────────────
# Only local dev and the production site; ALLOWED_ORIGINS overrides for other
# deployments (e.g. a Vercel preview URL) without a code change.
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000,https://volterraai.com,https://www.volterraai.com"
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(scans_router, prefix="/api/scans")
app.include_router(journal_router, prefix="/api/journal")
app.include_router(users_router, prefix="/api/users")
app.include_router(analytics_router, prefix="/api/analytics")
app.include_router(ticker_router, prefix="/api/ticker")
app.include_router(alerts_router, prefix="/api/alerts")
app.include_router(demo_router, prefix="/api/demo")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(tz=timezone.utc).isoformat()}

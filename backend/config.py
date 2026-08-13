# Launch-level feature flags.
#
# BILLING_ENABLED gates everything that assumes a paid Pro tier exists:
# digest eligibility windows and the Pro-only test-alert endpoint. The first
# launch is free-tier-only with no Stripe integration, so it defaults to
# False — every signed-in user gets full access. Flip it (and the frontend's
# NEXT_PUBLIC_PAYWALL_ENABLED, which must be flipped together) once paid
# plans actually exist, and the tiering logic below comes back to life.
import os

from dotenv import load_dotenv

load_dotenv()

BILLING_ENABLED: bool = os.getenv("BILLING_ENABLED", "false").lower() == "true"

# Free users keep receiving the digest for this many days after signup —
# only applied when BILLING_ENABLED is True.
FREE_DIGEST_DAYS: int = 30

# ── Market data provider ─────────────────────────────────────────────────────
# Tradier is the production source: a real market-data API with an API key,
# rather than yfinance's unofficial Yahoo scraping (which gets rate-limited
# from cloud IPs like Railway's). Defaults to Tradier whenever a key is
# present, so setting TRADIER_API_KEY is all it takes to switch; force either
# side with MARKET_DATA_PROVIDER=tradier|yfinance.
TRADIER_API_KEY: str = os.getenv("TRADIER_API_KEY", "")
TRADIER_BASE_URL: str = os.getenv(
    "TRADIER_BASE_URL", "https://sandbox.tradier.com/v1"
).rstrip("/")

MARKET_DATA_PROVIDER: str = os.getenv(
    "MARKET_DATA_PROVIDER", "tradier" if TRADIER_API_KEY else "yfinance"
).lower()


def use_tradier() -> bool:
    """True when live calls should go to Tradier rather than yfinance."""
    return MARKET_DATA_PROVIDER == "tradier" and bool(TRADIER_API_KEY)

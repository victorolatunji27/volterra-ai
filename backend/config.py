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

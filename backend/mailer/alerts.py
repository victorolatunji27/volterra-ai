# Plain-text strategy alert emails, sent directly via the Resend HTTP API.
#
# Unlike the digest (HTML via the sync resend SDK), alerts are sent with
# httpx.AsyncClient so the async scan pipeline never blocks the event loop.
import logging
import os

import httpx
import sentry_sdk
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
ALERT_FROM_ADDRESS: str = os.getenv("ALERT_FROM_ADDRESS", "alerts@volterraai.com")
RESEND_EMAILS_URL = "https://api.resend.com/emails"


def build_alert_subject(tickers: list[str]) -> str:
    return f"VolterraAI alert — {', '.join(tickers)} match your strategy"


def build_alert_text(matches: list[dict]) -> str:
    """
    Plain-text body: one line per matched setup with its strategy tags and
    OI ratio. No HTML — alert emails are text only.
    """
    lines = ["These setups match your strategy preferences:", ""]
    for m in matches:
        tags = ", ".join(m.get("strategy_tags") or []) or "untagged"
        oi = m.get("oi_ratio")
        oi_str = f"{oi:.1f}x" if isinstance(oi, (int, float)) else "n/a"
        lines.append(f"- {m['ticker']} — {tags} — OI ratio {oi_str}")
    lines += [
        "",
        "Not financial advice. VolterraAI provides analysis tools, not recommendations.",
    ]
    return "\n".join(lines)


async def send_alert_email(to: str, subject: str, text: str) -> bool:
    """
    POST one plain-text email to the Resend API. Returns True on success.

    Failures are logged and captured to Sentry but never raised — a failed
    alert must not crash the scan pipeline.
    """
    if not RESEND_API_KEY:
        logger.error("send_alert_email: RESEND_API_KEY is not set — cannot send to %s.", to)
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": ALERT_FROM_ADDRESS, "to": [to], "subject": subject, "text": text},
            )
    except Exception as exc:
        logger.error("send_alert_email(%s): request failed — %s", to, exc, exc_info=True)
        sentry_sdk.capture_exception(exc)
        return False

    if response.status_code >= 400:
        detail = response.text[:200]
        logger.error(
            "send_alert_email(%s): Resend returned HTTP %d — %s",
            to, response.status_code, detail,
        )
        sentry_sdk.capture_message(
            f"Resend alert send failed for {to}: HTTP {response.status_code} {detail}",
            level="error",
        )
        return False

    logger.info("send_alert_email(%s): sent (%s).", to, subject)
    return True

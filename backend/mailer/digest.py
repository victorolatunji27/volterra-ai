# Builds and sends the daily market digest email to subscribed users.
import logging
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
DIGEST_FROM_ADDRESS: str = os.getenv("DIGEST_FROM_ADDRESS", "VolterraAI <digest@volterraai.com>")

MAX_DIGEST_ENTRIES = 5


def build_digest_subject(for_date: date | None = None) -> str:
    """Return the digest subject line for *for_date* (default: today)."""
    d = for_date or date.today()
    return f"VolterraAI Morning Brief — {d.strftime('%B %-d, %Y')}"


def _flow_dot_color(call_put_ratio: float | None) -> str:
    """Green for call-heavy flow, red for put-heavy, gray otherwise."""
    if call_put_ratio is None:
        return "#9ca3af"
    if call_put_ratio > 1.5:
        return "#16a34a"
    if call_put_ratio < 0.7:
        return "#dc2626"
    return "#9ca3af"


def _scan_block(scan: dict) -> str:
    """Render one scan entry as an inline-styled HTML table row block."""
    ticker = scan.get("ticker", "?")
    price = scan.get("price_at_scan")
    price_str = f"${price:,.2f}" if isinstance(price, (int, float)) else "N/A"
    oi_ratio = scan.get("oi_ratio") or 0.0
    dot_color = _flow_dot_color(scan.get("call_put_ratio"))
    setup_summary = scan.get("setup_summary") or "No AI summary available for this scan."
    risk_note = scan.get("risk_note") or ""

    risk_block = ""
    if risk_note:
        risk_block = (
            '<tr><td style="padding: 8px 0 0 0;">'
            '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="background-color: #f3f4f6; padding: 10px 12px; '
            'font-family: Arial, sans-serif; font-size: 13px; color: #4b5563; '
            f'line-height: 18px;"><strong>Risk:</strong> {risk_note}</td></tr>'
            "</table></td></tr>"
        )

    return (
        '<tr><td style="padding: 16px 0;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        "<tr>"
        '<td style="font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; '
        'color: #111827;">'
        f'<span style="display: inline-block; width: 10px; height: 10px; '
        f'border-radius: 5px; background-color: {dot_color};">&nbsp;</span>'
        f"&nbsp;{ticker} &nbsp;"
        f'<span style="font-size: 14px; font-weight: normal; color: #6b7280;">{price_str}</span>'
        "</td>"
        '<td align="right" style="font-family: Arial, sans-serif; font-size: 12px;">'
        '<span style="background-color: #eef2ff; color: #4338ca; padding: 3px 8px; '
        f'border-radius: 10px;">{oi_ratio:.1f}x unusual</span>'
        "</td>"
        "</tr>"
        '<tr><td colspan="2" style="padding: 8px 0 0 0; font-family: Arial, sans-serif; '
        f'font-size: 14px; color: #374151; line-height: 20px;">{setup_summary}</td></tr>'
        f"{risk_block}"
        '<tr><td colspan="2" style="padding: 10px 0 0 0; font-family: Arial, sans-serif; '
        'font-size: 13px;">'
        f'<a href="https://volterraai.com/ticker/{ticker}" style="color: #4338ca; '
        'text-decoration: none;">View in VolterraAI &rarr;</a>'
        "</td></tr>"
        "</table>"
        "</td></tr>"
        '<tr><td style="border-bottom: 1px solid #e5e7eb; font-size: 0; line-height: 0;">&nbsp;</td></tr>'
    )


def build_digest_html(scans: list[dict]) -> str:
    """
    Generate the morning-brief HTML email body for up to 5 scans.

    Each scan dict should contain: ticker, price_at_scan, call_put_ratio,
    oi_ratio, setup_summary, risk_note.

    Follows HTML-email constraints: inline CSS only, table layout,
    600px max width, white background, Arial, pixel units, no JS or images.
    """
    today_str = date.today().strftime("%A, %B %-d, %Y")
    entries = "".join(_scan_block(s) for s in scans[:MAX_DIGEST_ENTRIES])

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color: #ffffff;"><tr><td align="center" style="padding: 24px 12px;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="max-width: 600px; width: 100%;">'
        # Header
        '<tr><td style="font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; '
        'color: #111827; padding-bottom: 2px;">VolterraAI</td></tr>'
        '<tr><td style="font-family: Arial, sans-serif; font-size: 14px; color: #6b7280; '
        f'padding-bottom: 4px;">Options Flow Morning Brief &middot; {today_str}</td></tr>'
        '<tr><td style="border-bottom: 2px solid #111827; font-size: 0; line-height: 0;">&nbsp;</td></tr>'
        # Intro
        '<tr><td style="font-family: Arial, sans-serif; font-size: 14px; color: #374151; '
        'padding: 16px 0 4px 0;">Good morning. Here are today\'s 5 most unusual options setups.</td></tr>'
        # Entries
        f"{entries}"
        # Footer
        '<tr><td style="font-family: Arial, sans-serif; font-size: 12px; color: #9ca3af; '
        'padding: 24px 0 6px 0; line-height: 17px;">This is not financial advice. '
        "VolterraAI provides analysis tools, not recommendations.</td></tr>"
        '<tr><td style="font-family: Arial, sans-serif; font-size: 12px; color: #9ca3af;">'
        'Manage email preferences: <a href="{preferences_link}" style="color: #6b7280;">'
        "{preferences_link}</a></td></tr>"
        "</table></td></tr></table>"
    )


def send_digest(recipients: list[str], html: str, subject: str) -> bool:
    """
    Send *html* to *recipients* via Resend. Returns True on success.

    Imports resend lazily so the rest of the mailer works (and tests run)
    without the SDK installed or RESEND_API_KEY set.
    """
    if not recipients:
        logger.warning("send_digest: no recipients — skipping send.")
        return False

    if not RESEND_API_KEY:
        logger.error("send_digest: RESEND_API_KEY is not set — cannot send.")
        return False

    try:
        import resend
    except ImportError:
        logger.error("send_digest: resend package is not installed.")
        return False

    resend.api_key = RESEND_API_KEY

    try:
        result = resend.Emails.send({
            "from": DIGEST_FROM_ADDRESS,
            "to": recipients,
            "subject": subject,
            "html": html,
        })
        logger.info(
            "send_digest: sent to %d recipient(s), resend id=%s",
            len(recipients), (result or {}).get("id"),
        )
        return True
    except Exception as exc:
        logger.error("send_digest: Resend send failed — %s", exc, exc_info=True)
        return False

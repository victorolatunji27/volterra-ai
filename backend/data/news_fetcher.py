# Fetches raw financial news articles and headlines from external news APIs.
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NEWSAPI_KEY: str      = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_BASE_URL: str = os.getenv("NEWSAPI_BASE_URL", "https://newsapi.org/v2").rstrip("/")

MIN_DESCRIPTION_LENGTH = 30
MIN_USABLE_RESULTS     = 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_news_for_ticker(ticker: str) -> list[dict]:
    """
    Fetch the 5 most recent news articles for *ticker* from NewsAPI.

    Articles where the description is missing or shorter than
    MIN_DESCRIPTION_LENGTH characters are discarded.  If fewer than
    MIN_USABLE_RESULTS articles survive the filter, an empty list is
    returned and a warning is logged.

    Args:
        ticker: The equity symbol to search for (e.g. "AAPL").

    Returns:
        A list of up to 5 article dicts, each containing:
            title, description, url, published_at, source
        Returns an empty list on any unrecoverable error.
    """
    if not NEWSAPI_KEY:
        logger.error("fetch_news_for_ticker(%s): NEWSAPI_KEY is not set.", ticker)
        return []

    params = {
        "q":         ticker,
        "sortBy":    "publishedAt",
        "pageSize":  5,
        "language":  "en",
        "apiKey":    NEWSAPI_KEY,
    }

    # ── HTTP request ────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{NEWSAPI_BASE_URL}/everything", params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "fetch_news_for_ticker(%s): HTTP %s from NewsAPI — %s",
            ticker, exc.response.status_code, exc.response.text[:200],
        )
        return []
    except httpx.RequestError as exc:
        logger.error(
            "fetch_news_for_ticker(%s): network error reaching NewsAPI — %s", ticker, exc
        )
        return []

    # ── JSON parse ──────────────────────────────────────────────────────────
    try:
        payload = response.json()
    except Exception as exc:
        logger.error(
            "fetch_news_for_ticker(%s): failed to parse JSON response — %s", ticker, exc
        )
        return []

    if payload.get("status") != "ok":
        logger.error(
            "fetch_news_for_ticker(%s): NewsAPI returned status=%r, message=%r",
            ticker, payload.get("status"), payload.get("message"),
        )
        return []

    raw_articles: list[dict] = payload.get("articles") or []

    # ── Normalise & filter ──────────────────────────────────────────────────
    normalised: list[dict] = []
    for article in raw_articles:
        description = article.get("description") or ""
        if len(description.strip()) < MIN_DESCRIPTION_LENGTH:
            logger.debug(
                "fetch_news_for_ticker(%s): dropped article (short/missing description): %r",
                ticker, article.get("title"),
            )
            continue

        normalised.append({
            "title":        (article.get("title") or "").strip(),
            "description":  description.strip(),
            "url":          (article.get("url") or "").strip(),
            "published_at": (article.get("publishedAt") or "").strip(),
            "source":       (article.get("source") or {}).get("name") or "Unknown",
        })

    if len(normalised) < MIN_USABLE_RESULTS:
        logger.warning(
            "fetch_news_for_ticker(%s): only %d usable article(s) found after filtering "
            "(minimum required: %d) — returning empty list.",
            ticker, len(normalised), MIN_USABLE_RESULTS,
        )
        return []

    logger.info(
        "fetch_news_for_ticker(%s): returning %d article(s).", ticker, len(normalised)
    )
    return normalised


def format_news_for_prompt(news_list: list[dict]) -> str:
    """
    Format a list of news article dicts into a numbered plain-text block
    suitable for inclusion in an LLM prompt.

    Each line follows the pattern:
        [N] HEADLINE: ... | SOURCE: ... | DATE: ... | SUMMARY: ...

    Args:
        news_list: Output of fetch_news_for_ticker().

    Returns:
        A multi-line string, or an empty string if news_list is empty.
    """
    if not news_list:
        return ""

    lines: list[str] = []
    for i, article in enumerate(news_list, start=1):
        # Truncate long descriptions so the prompt stays concise
        summary = article.get("description", "")
        if len(summary) > 200:
            summary = summary[:197].rstrip() + "..."

        line = (
            f"[{i}] "
            f"HEADLINE: {article.get('title', 'N/A')} | "
            f"SOURCE: {article.get('source', 'Unknown')} | "
            f"DATE: {article.get('published_at', 'N/A')} | "
            f"SUMMARY: {summary}"
        )
        lines.append(line)

    return "\n".join(lines)

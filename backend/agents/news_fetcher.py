# Agent that retrieves and summarizes relevant financial news for a given ticker or sector.
import logging
import time
from datetime import date

import sentry_sdk
from dotenv import load_dotenv

from agents.flow_analyzer import _call_claude, _parse_json_block
from cache import cache_get_json, cache_set_json
from data.news_fetcher import format_news_for_prompt

load_dotenv()

logger = logging.getLogger(__name__)

SYNTHESIS_KEYS = {"catalyst_note", "contradiction_note"}

NEWS_SYSTEM_PROMPT = (
    "You are a financial news analyst. Given a list of recent headlines about a stock ticker, "
    "identify the most relevant potential catalyst and any contradicting signals. "
    "Return ONLY valid JSON with no extra text. "
    "Return: {catalyst_note: string max 60 words, contradiction_note: string max 40 words}"
)


async def synthesize_news(ticker: str, news_list: list[dict]) -> dict | None:
    """
    Synthesize raw headlines into a structured catalyst note via Claude.

    Returns {"catalyst_note": str, "contradiction_note": str}, cached in Redis
    for 1 hour (news moves faster than flow data). Returns None when
    news_list is empty or the response cannot be parsed.
    """
    if not news_list:
        logger.info("synthesize_news(%s): empty news list — skipping.", ticker)
        return None

    cache_key = f"news_summary:{ticker}:{date.today().isoformat()}"
    started = time.perf_counter()

    cached = await cache_get_json(cache_key)
    if cached is not None:
        logger.info(
            "synthesize_news(%s): cache HIT | latency_ms=%.0f",
            ticker, (time.perf_counter() - started) * 1000,
        )
        return cached

    user_message = (
        format_news_for_prompt(news_list)
        + f"\n\nTicker: {ticker}. Summarize the catalyst and any contradictions."
    )

    sentry_sdk.add_breadcrumb(
        category="agent", message=f"Synthesizing news for {ticker}", level="info"
    )
    try:
        raw, tokens_in, tokens_out = await _call_claude(
            NEWS_SYSTEM_PROMPT, user_message, temperature=0.2, max_tokens=200
        )
    except Exception as exc:
        logger.error("synthesize_news(%s): Claude call failed — %s", ticker, exc, exc_info=True)
        sentry_sdk.capture_exception(exc)
        return None

    result = _parse_json_block(raw)
    if not isinstance(result, dict) or not SYNTHESIS_KEYS <= result.keys():
        logger.error("synthesize_news(%s): invalid JSON response: %r", ticker, raw[:300])
        return None

    await cache_set_json(cache_key, result, ttl_seconds=3600)

    logger.info(
        "synthesize_news(%s): cache MISS | tokens_in=%d | tokens_out=%d | latency_ms=%.0f",
        ticker, tokens_in, tokens_out, (time.perf_counter() - started) * 1000,
    )
    return result

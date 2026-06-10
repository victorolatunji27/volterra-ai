# Agent that analyzes unusual options flow and flags high-conviction signals.
import json
import logging
import os
import time
from datetime import date

import sentry_sdk
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from cache import cache_get_json, cache_set_json
from db.models import AiSummary

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_VERSION = "claude-sonnet-4-20250514"

REQUIRED_FLOW_KEYS = {
    "ticker", "call_volume", "put_volume", "oi_ratio",
    "call_put_ratio", "avg_strike", "iv_rank", "price_at_scan",
}

ANALYSIS_KEYS = {"setup_summary", "flow_interpretation", "risk_note"}

FLOW_SYSTEM_PROMPT = """You are a financial analyst assistant for VolterraAI. Your job is to analyze options flow data
and news to identify possible trade setups for retail traders.

Rules you must follow:
- Do not predict stock prices
- Do not give financial advice
- Always note uncertainty and risk
- Be specific about what the data shows, not what you think will happen
- Return ONLY valid JSON with no extra text, no markdown, no code fences

Return a JSON object with exactly these keys:
- setup_summary: string, max 150 words, plain English explanation of the setup
- flow_interpretation: string, max 80 words, what the options flow data specifically suggests
- risk_note: string, max 60 words, specific risks or reasons this setup could fail

Few-shot examples:
[Example 1]
Input: {"ticker": "NVDA", "call_volume": 45000, "put_volume": 8000, "oi_ratio": 4.2,
        "call_put_ratio": 5.6, "avg_strike": 520, "iv_rank": 68, "price_at_scan": 498}
Output: {"setup_summary": "NVDA is showing heavily skewed call buying with a 5.6 call/put ratio and a volume-to-OI ratio of 4.2x the baseline. The average strike of $520 suggests traders are positioning for a move above current price within the current expiry window. IV rank at 68 means options are moderately expensive relative to the past year, which reduces the margin for error on long premium plays.", "flow_interpretation": "Call volume is 5.6x put volume. The flow is concentrated above current price, indicating directional bullish positioning rather than hedging. No clear put buying to suggest institutional protection.", "risk_note": "IV at 68 makes long calls expensive. A failure to move toward the $520 strike quickly will erode premium. Broader market weakness could override any stock-specific catalyst."}

[Example 2]
Input: {"ticker": "META", "call_volume": 12000, "put_volume": 31000, "oi_ratio": 6.1,
        "call_put_ratio": 0.38, "avg_strike": 445, "iv_rank": 45, "price_at_scan": 468}
Output: {"setup_summary": "META has unusually heavy put volume at 6.1x the OI baseline, with the average strike at $445 — roughly 5% below current price. This is consistent with either directional bearish bets or protective hedging ahead of a catalyst. IV rank at 45 is moderate, so options pricing is not extreme in either direction.", "flow_interpretation": "Put volume is 2.6x call volume with strike clustering below current price. This could be institutional hedging or outright short positioning. Without a clear catalyst, the direction is ambiguous.", "risk_note": "Put heavy flow on large-caps often reflects portfolio hedging, not directional conviction. The setup fails if no catalyst materializes and the stock continues higher."}

[Example 3]
Input: {"ticker": "AMD", "call_volume": 28000, "put_volume": 29500, "oi_ratio": 1.1,
        "call_put_ratio": 0.95, "avg_strike": 162, "iv_rank": 22, "price_at_scan": 161}
Output: {"setup_summary": "AMD shows near-equal call and put volume with a volume-to-OI ratio of only 1.1x — barely above normal activity. IV rank at 22 indicates options are cheap relative to historical ranges, which may favor buyers of premium if a move develops. There is no clear directional signal in the current flow.", "flow_interpretation": "Call and put volumes are roughly equal. No unusual directional skew. Low OI ratio suggests this is routine activity, not unusual positioning.", "risk_note": "No clear signal means any trade here is speculative. Low IV is attractive for buyers but meaningless without a thesis."}"""

STRATEGY_TAGS = [
    "momentum", "earnings_play", "iv_crush", "breakout", "hedge", "contrarian", "neutral",
]

TAGGER_SYSTEM_PROMPT = """You are a strategy classifier for options trade setups.
Given a setup summary and flow data, assign 1-2 strategy tags from this exact list:
momentum, earnings_play, iv_crush, breakout, hedge, contrarian, neutral
Return ONLY a JSON array of strings. No explanation. No other text.
If the setup is ambiguous, return ["neutral"].

Rules:
- Never assign more than 2 tags
- earnings_play requires explicit mention of an earnings catalyst
- iv_crush requires IV rank > 70
- hedge requires put volume > 2x call volume on a stock trending up

Few-shot examples:
[Example 1]
Input: {"setup_summary": "NVDA is showing heavily skewed call buying with flow concentrated above current price ahead of next week's earnings report. IV rank at 82 is near annual highs.", "oi_ratio": 4.2, "call_put_ratio": 5.6, "iv_rank": 82}
Output: ["earnings_play", "iv_crush"]

[Example 2]
Input: {"setup_summary": "AAPL put volume is 2.8x call volume while the stock sits near all-time highs after a steady two-month uptrend. Strikes cluster 5% below spot.", "oi_ratio": 3.1, "call_put_ratio": 0.36, "iv_rank": 40}
Output: ["hedge"]

[Example 3]
Input: {"setup_summary": "COIN call flow is concentrated at strikes 10% above the recent consolidation range high, with volume 6x open interest and a strong recent price trend.", "oi_ratio": 6.0, "call_put_ratio": 4.1, "iv_rank": 55}
Output: ["breakout", "momentum"]

[Example 4]
Input: {"setup_summary": "AMD shows near-equal call and put volume with a volume-to-OI ratio of only 1.1x. There is no clear directional signal in the current flow.", "oi_ratio": 1.1, "call_put_ratio": 0.95, "iv_rank": 22}
Output: ["neutral"]"""

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    """Lazily build the Anthropic client so imports work without an API key."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _parse_json_block(raw: str) -> dict | list | None:
    """Parse a JSON object/array from raw model output, tolerating code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # Drop a possible leading language hint like "json\n"
        first_newline = text.find("\n")
        if first_newline != -1 and text[:first_newline].strip().lower() in ("json", ""):
            text = text[first_newline + 1:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _call_claude(
    system: str,
    user_content: str,
    temperature: float,
    max_tokens: int,
    retry_message: str | None = None,
    prior_response: str | None = None,
) -> tuple[str, int, int]:
    """
    Single Claude messages call. Returns (text, tokens_in, tokens_out).
    When retrying, the prior exchange is replayed so the model sees its mistake.
    """
    messages: list[dict] = [{"role": "user", "content": user_content}]
    if retry_message and prior_response is not None:
        messages.append({"role": "assistant", "content": prior_response})
        messages.append({"role": "user", "content": retry_message})

    response = await _get_client().messages.create(
        model=MODEL_VERSION,
        system=system,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return text, response.usage.input_tokens, response.usage.output_tokens


async def analyze_flow(flow_scan: dict) -> dict | None:
    """
    Analyze one ticker's options flow with Claude and return a structured dict
    with setup_summary, flow_interpretation, and risk_note.

    Results are cached in Redis for 24h under flow_summary:{ticker}:{date}.
    Returns None on malformed input or if the model fails to produce valid
    JSON after one retry.
    """
    if not isinstance(flow_scan, dict):
        logger.error("analyze_flow: input is not a dict.")
        return None

    missing = REQUIRED_FLOW_KEYS - flow_scan.keys()
    if missing:
        logger.error("analyze_flow: input missing required keys: %s", sorted(missing))
        return None

    ticker = flow_scan["ticker"]
    cache_key = f"flow_summary:{ticker}:{date.today().isoformat()}"

    started = time.perf_counter()

    cached = await cache_get_json(cache_key)
    if cached is not None:
        logger.info(
            "analyze_flow(%s): cache HIT | latency_ms=%.0f",
            ticker, (time.perf_counter() - started) * 1000,
        )
        return cached

    payload = json.dumps({k: flow_scan[k] for k in sorted(REQUIRED_FLOW_KEYS)})
    sentry_sdk.add_breadcrumb(
        category="agent", message=f"Analyzing {ticker}", level="info"
    )

    tokens_in = tokens_out = 0
    try:
        raw, tokens_in, tokens_out = await _call_claude(
            FLOW_SYSTEM_PROMPT, payload, temperature=0.3, max_tokens=500
        )
        result = _parse_json_block(raw)

        if not isinstance(result, dict) or not ANALYSIS_KEYS <= result.keys():
            logger.warning(
                "analyze_flow(%s): invalid JSON on first attempt, retrying. Raw: %r",
                ticker, raw[:300],
            )
            raw_retry, retry_in, retry_out = await _call_claude(
                FLOW_SYSTEM_PROMPT, payload, temperature=0.3, max_tokens=500,
                retry_message="Your previous response was not valid JSON. Return ONLY a JSON object.",
                prior_response=raw,
            )
            tokens_in += retry_in
            tokens_out += retry_out
            result = _parse_json_block(raw_retry)
            if not isinstance(result, dict) or not ANALYSIS_KEYS <= result.keys():
                logger.error(
                    "analyze_flow(%s): invalid JSON after retry. Raw: %r",
                    ticker, raw_retry[:300],
                )
                return None
    except Exception as exc:
        logger.error("analyze_flow(%s): Claude call failed — %s", ticker, exc, exc_info=True)
        return None

    await cache_set_json(cache_key, result, ttl_seconds=86400)

    logger.info(
        "analyze_flow(%s): cache MISS | tokens_in=%d | tokens_out=%d | latency_ms=%.0f",
        ticker, tokens_in, tokens_out, (time.perf_counter() - started) * 1000,
    )
    return result


async def store_summary(
    flow_scan_id: int,
    analysis: dict,
    news: dict | None,
    db_session,
) -> int:
    """
    Persist one AI analysis as an ai_summaries row and return its new ID.
    """
    summary = AiSummary(
        flow_scan_id=flow_scan_id,
        setup_summary=analysis.get("setup_summary"),
        flow_interpretation=analysis.get("flow_interpretation"),
        risk_note=analysis.get("risk_note"),
        news_used=news,
        model_version=MODEL_VERSION,
        strategy_tags=analysis.get("strategy_tags"),
    )
    db_session.add(summary)
    await db_session.flush()
    summary_id = summary.id
    await db_session.commit()
    return summary_id


async def tag_strategy(summary: dict) -> list[str]:
    """
    Classify an AI summary into 1-2 strategy tags from STRATEGY_TAGS.

    Expects a dict with at least setup_summary, plus flow context
    (oi_ratio, call_put_ratio, iv_rank) and optionally flow_scan_id for
    caching. Returns ["neutral"] on any failure.
    """
    flow_scan_id = summary.get("flow_scan_id")
    cache_key = f"strategy_tags:{flow_scan_id}" if flow_scan_id else None

    if cache_key:
        cached = await cache_get_json(cache_key)
        if isinstance(cached, list):
            return cached

    payload = json.dumps({
        "setup_summary": summary.get("setup_summary", ""),
        "oi_ratio": summary.get("oi_ratio"),
        "call_put_ratio": summary.get("call_put_ratio"),
        "iv_rank": summary.get("iv_rank"),
    })

    sentry_sdk.add_breadcrumb(
        category="agent", message="Tagging strategy", level="info"
    )
    try:
        raw, _, _ = await _call_claude(
            TAGGER_SYSTEM_PROMPT, payload, temperature=0.2, max_tokens=100
        )
        tags = _parse_json_block(raw)
    except Exception as exc:
        logger.error("tag_strategy: Claude call failed — %s", exc, exc_info=True)
        return ["neutral"]

    if not isinstance(tags, list):
        logger.error("tag_strategy: response was not a JSON array: %r", str(tags)[:200])
        return ["neutral"]

    # confidence_check: drop any tag outside the allowed taxonomy
    valid: list[str] = []
    for tag in tags:
        if tag in STRATEGY_TAGS:
            valid.append(tag)
        else:
            logger.warning("tag_strategy: classification anomaly — removed tag %r", tag)

    valid = valid[:2] or ["neutral"]

    if cache_key:
        await cache_set_json(cache_key, valid, ttl_seconds=86400)

    return valid

# Tests for agent logic — flow analysis, news summarization, and brief composition.
#
# No real API calls are made: the Anthropic SDK is mocked with unittest.mock,
# and the Upstash cache helpers are patched to behave as a permanent miss.
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.flow_analyzer import analyze_flow
from data.market_data import get_price_history
from data.news_fetcher import format_news_for_prompt
from scheduler.daily_scan import validate_flow_scan

VALID_FLOW = {
    "ticker": "NVDA", "call_volume": 45000, "put_volume": 8000,
    "oi_ratio": 4.2, "call_put_ratio": 5.6, "avg_strike": 520,
    "iv_rank": 68, "price_at_scan": 498,
}

VALID_ANALYSIS = {
    "setup_summary": "Heavy call buying.",
    "flow_interpretation": "Bullish skew.",
    "risk_note": "IV is elevated.",
}


def _mock_anthropic_response(payload: str) -> MagicMock:
    """Build a fake anthropic Messages response carrying *payload* as text."""
    block = MagicMock()
    block.type = "text"
    block.text = payload
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


def _patch_no_cache():
    """Patch the cache used inside flow_analyzer to always miss and discard writes."""
    return (
        patch("agents.flow_analyzer.cache_get_json", new=AsyncMock(return_value=None)),
        patch("agents.flow_analyzer.cache_set_json", new=AsyncMock(return_value=False)),
    )


# ---------------------------------------------------------------------------
# analyze_flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_flow_returns_none_on_malformed_input():
    # Missing required keys must short-circuit before any API call
    assert await analyze_flow({"ticker": "NVDA"}) is None
    assert await analyze_flow({}) is None
    assert await analyze_flow("not a dict") is None


@pytest.mark.asyncio
async def test_analyze_flow_parses_valid_json_response():
    get_patch, set_patch = _patch_no_cache()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(json.dumps(VALID_ANALYSIS))
    )
    with get_patch, set_patch, patch(
        "agents.flow_analyzer._get_client", return_value=mock_client
    ):
        result = await analyze_flow(VALID_FLOW)

    assert result == VALID_ANALYSIS
    mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_flow_retries_once_then_returns_none():
    get_patch, set_patch = _patch_no_cache()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response("I am not JSON")
    )
    with get_patch, set_patch, patch(
        "agents.flow_analyzer._get_client", return_value=mock_client
    ):
        result = await analyze_flow(VALID_FLOW)

    assert result is None
    # One initial attempt + exactly one retry
    assert mock_client.messages.create.await_count == 2


# ---------------------------------------------------------------------------
# format_news_for_prompt
# ---------------------------------------------------------------------------

def test_format_news_for_prompt_formats_valid_input():
    news = [
        {
            "title": "NVDA hits record high",
            "description": "Shares rallied after a strong datacenter quarter.",
            "url": "https://example.com/1",
            "published_at": "2026-06-09T12:00:00Z",
            "source": "Reuters",
        },
        {
            "title": "Analysts raise targets",
            "description": "Multiple banks lifted price targets this morning.",
            "url": "https://example.com/2",
            "published_at": "2026-06-09T13:00:00Z",
            "source": "Bloomberg",
        },
    ]
    formatted = format_news_for_prompt(news)
    lines = formatted.split("\n")

    assert len(lines) == 2
    assert lines[0].startswith("[1] HEADLINE: NVDA hits record high | SOURCE: Reuters")
    assert "DATE: 2026-06-09T12:00:00Z" in lines[0]
    assert "SUMMARY: Shares rallied" in lines[0]
    assert lines[1].startswith("[2] ")
    assert format_news_for_prompt([]) == ""


# ---------------------------------------------------------------------------
# validate_flow_scan
# ---------------------------------------------------------------------------

def test_validate_flow_scan_rejects_negative_oi_ratio():
    bad = {
        "ticker": "NVDA", "oi_ratio": -1.0,
        "call_volume": 100, "put_volume": 50, "price_at_scan": 500.0,
    }
    assert validate_flow_scan(bad) is False


def test_validate_flow_scan_accepts_valid_data():
    good = {
        "ticker": "NVDA", "oi_ratio": 4.2,
        "call_volume": 100, "put_volume": 0, "price_at_scan": 500.0,
    }
    assert validate_flow_scan(good) is True


def test_validate_flow_scan_rejects_bad_shapes():
    assert validate_flow_scan({}) is False
    assert validate_flow_scan("nope") is False
    assert validate_flow_scan({
        "ticker": "", "oi_ratio": 1.0,
        "call_volume": 1, "put_volume": 1, "price_at_scan": 1.0,
    }) is False
    assert validate_flow_scan({
        "ticker": "NVDA", "oi_ratio": 1.0,
        "call_volume": -5, "put_volume": 1, "price_at_scan": 1.0,
    }) is False
    assert validate_flow_scan({
        "ticker": "NVDA", "oi_ratio": 1.0,
        "call_volume": 1, "put_volume": 1, "price_at_scan": 0,
    }) is False


# ---------------------------------------------------------------------------
# get_price_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_price_history_returns_series_and_caches():
    series = [{"date": "2026-06-01", "close": 100.0}]
    with patch("data.market_data.cache_get_json", new=AsyncMock(return_value=None)), \
         patch("data.market_data.cache_set_json", new=AsyncMock(return_value=True)) as set_mock, \
         patch("data.market_data._fetch_price_history", return_value=series):
        result = await get_price_history("NVDA", days=30)

    assert result == series
    # Cached under the price_history key with a 24h TTL
    set_mock.assert_awaited_once()
    assert set_mock.await_args.args[0].startswith("price_history:NVDA:")
    assert set_mock.await_args.kwargs["ttl_seconds"] == 86400


@pytest.mark.asyncio
async def test_get_price_history_returns_cached_without_fetch():
    cached = [{"date": "2026-06-01", "close": 100.0}]
    with patch("data.market_data.cache_get_json", new=AsyncMock(return_value=cached)), \
         patch("data.market_data._fetch_price_history") as fetch_mock:
        result = await get_price_history("NVDA")

    assert result == cached
    fetch_mock.assert_not_called()  # cache hit — no yfinance call


@pytest.mark.asyncio
async def test_get_price_history_returns_none_on_failure():
    with patch("data.market_data.cache_get_json", new=AsyncMock(return_value=None)), \
         patch("data.market_data.cache_set_json", new=AsyncMock(return_value=True)), \
         patch("data.market_data._fetch_price_history", side_effect=RuntimeError("boom")):
        result = await get_price_history("NVDA")

    assert result is None

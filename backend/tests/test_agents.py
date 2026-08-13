# Tests for agent logic — flow analysis, news summarization, and brief composition.
#
# No real API calls are made: the Anthropic SDK is mocked with unittest.mock,
# and the Upstash cache helpers are patched to behave as a permanent miss.
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.flow_analyzer import analyze_flow
from agents.journal_agent import EMPTY_REVIEW, generate_weekly_review
from data.market_data import get_price_history
from data.news_fetcher import format_news_for_prompt
from scheduler.daily_scan import match_alerts, validate_flow_scan

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


# ---------------------------------------------------------------------------
# match_alerts
# ---------------------------------------------------------------------------

class _FakeAlertSession:
    """Async-context session stub for match_alerts: canned users, records adds."""

    def __init__(self, users):
        self._users = users
        self.added = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *args, **kwargs):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self._users))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_match_alerts_writes_row_and_sends_email():
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", strategy_tags=["momentum"])
    session = _FakeAlertSession([user])
    scans = [
        {"ticker": "NVDA", "strategy_tags": ["momentum"], "oi_ratio": 4.1},
        {"ticker": "META", "strategy_tags": ["hedge"], "oi_ratio": 2.0},
        {"ticker": "AMD", "strategy_tags": [], "oi_ratio": 1.1},   # untagged — ignored
    ]
    with patch("scheduler.daily_scan.async_session", return_value=session), \
         patch(
             "scheduler.daily_scan._todays_scans_with_summaries",
             new=AsyncMock(return_value=scans),
         ), \
         patch(
             "scheduler.daily_scan.send_alert_email", new=AsyncMock(return_value=True)
         ) as send_mock:
        written = await match_alerts()

    assert written == 1
    assert len(session.added) == 1
    row = session.added[0]
    assert row.tickers == ["NVDA"]            # only the momentum match
    assert row.user_id == user.id
    assert session.committed is True

    # The matched setups are emailed as plain text to the user.
    send_mock.assert_awaited_once()
    to, subject, text = send_mock.await_args.args
    assert to == "a@b.com"
    assert subject == "VolterraAI alert — NVDA match your strategy"
    assert "NVDA — momentum — OI ratio 4.1x" in text


@pytest.mark.asyncio
async def test_match_alerts_records_row_even_if_email_fails():
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", strategy_tags=["momentum"])
    session = _FakeAlertSession([user])
    scans = [{"ticker": "NVDA", "strategy_tags": ["momentum"], "oi_ratio": 4.1}]
    with patch("scheduler.daily_scan.async_session", return_value=session), \
         patch(
             "scheduler.daily_scan._todays_scans_with_summaries",
             new=AsyncMock(return_value=scans),
         ), \
         patch("scheduler.daily_scan.send_alert_email", new=AsyncMock(return_value=False)):
        written = await match_alerts()

    # Email failed, but the alert_log row is still recorded and committed.
    assert written == 1
    assert len(session.added) == 1
    assert session.committed is True


@pytest.mark.asyncio
async def test_match_alerts_no_users_returns_zero():
    session = _FakeAlertSession([])
    with patch("scheduler.daily_scan.async_session", return_value=session), \
         patch(
             "scheduler.daily_scan._todays_scans_with_summaries",
             new=AsyncMock(return_value=[]),
         ):
        assert await match_alerts() == 0
    assert session.added == []


# ---------------------------------------------------------------------------
# Tradier provider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tradier_quote_parses_and_falls_back_across_fields():
    import data.market_data as md

    # `last` is present during market hours...
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value={"quotes": {"quote": {"last": 172.4, "close": 170.0}}})):
        assert await md._fetch_current_price_tradier("NVDA") == 172.4

    # ...and absent outside them, where close/prevclose carry the session.
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value={"quotes": {"quote": {"last": None, "close": 170.0}}})):
        assert await md._fetch_current_price_tradier("NVDA") == 170.0

    # Unknown symbol / empty payload degrades to None, never raises.
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value={"quotes": {"quote": None}})):
        assert await md._fetch_current_price_tradier("NOPE") is None
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value=None)):
        assert await md._fetch_current_price_tradier("NVDA") is None


@pytest.mark.asyncio
async def test_tradier_history_parses_list_and_single_day():
    import data.market_data as md

    payload = {"history": {"day": [
        {"date": "2026-07-01", "close": 170.0},
        {"date": "2026-07-02", "close": 172.4},
    ]}}
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value=payload)):
        series = await md._fetch_price_history_tradier("NVDA", 30)
    assert series == [
        {"date": "2026-07-01", "close": 170.0},
        {"date": "2026-07-02", "close": 172.4},
    ]

    # A single-day range comes back unwrapped rather than as a list.
    single = {"history": {"day": {"date": "2026-07-02", "close": 172.4}}}
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value=single)):
        assert await md._fetch_price_history_tradier("NVDA", 1) == [{"date": "2026-07-02", "close": 172.4}]

    # Unknown symbol → history: null.
    with patch.object(md, "_tradier_get", new=AsyncMock(return_value={"history": None})):
        assert await md._fetch_price_history_tradier("NOPE", 30) is None


@pytest.mark.asyncio
async def test_get_current_price_dispatches_on_provider():
    import data.market_data as md

    with patch.object(md, "use_tradier", return_value=True), patch.object(
        md, "_fetch_current_price_tradier", new=AsyncMock(return_value=1.23)
    ) as tradier, patch.object(md, "_fetch_current_price") as yf_impl:
        assert await md.get_current_price("NVDA") == 1.23
    tradier.assert_awaited_once()
    yf_impl.assert_not_called()

    with patch.object(md, "use_tradier", return_value=False), patch.object(
        md, "_fetch_current_price", return_value=4.56
    ) as yf_impl:
        assert await md.get_current_price("NVDA") == 4.56
    yf_impl.assert_called_once()


@pytest.mark.asyncio
async def test_flow_fetch_falls_back_to_yfinance_when_tradier_returns_nothing():
    import data.options_fetcher as of

    yf_rows = [{"ticker": "NVDA", "oi_ratio": 4.1}]
    with patch.object(of, "use_tradier", return_value=True), patch.object(
        of, "fetch_unusual_options_flow", new=AsyncMock(return_value=[])
    ), patch.object(of, "fetch_options_flow_yfinance", new=AsyncMock(return_value=yf_rows)):
        # An empty Tradier result must not look like "no unusual activity".
        assert await of.fetch_options_flow() == yf_rows

    tradier_rows = [{"ticker": "TSLA", "oi_ratio": 2.2}]
    with patch.object(of, "use_tradier", return_value=True), patch.object(
        of, "fetch_unusual_options_flow", new=AsyncMock(return_value=tradier_rows)
    ), patch.object(of, "fetch_options_flow_yfinance", new=AsyncMock()) as yf_impl:
        assert await of.fetch_options_flow() == tradier_rows
    yf_impl.assert_not_awaited()


# ---------------------------------------------------------------------------
# send_alert_email / build_alert_text
# ---------------------------------------------------------------------------

def _mock_async_client(response):
    """AsyncClient context-manager mock whose post() returns *response*."""
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


def test_build_alert_text_lists_tickers_tags_and_oi():
    from mailer.alerts import build_alert_text
    text = build_alert_text([
        {"ticker": "NVDA", "strategy_tags": ["momentum", "breakout"], "oi_ratio": 4.1},
        {"ticker": "SPY", "strategy_tags": [], "oi_ratio": None},
    ])
    assert "- NVDA — momentum, breakout — OI ratio 4.1x" in text
    assert "- SPY — untagged — OI ratio n/a" in text
    assert "<" not in text  # plain text, no HTML
    assert "Not financial advice" in text


@pytest.mark.asyncio
async def test_send_alert_email_posts_to_resend():
    import mailer.alerts as alerts
    ctx, client = _mock_async_client(SimpleNamespace(status_code=200, text="{}"))
    with patch.object(alerts, "RESEND_API_KEY", "re_test"), \
         patch.object(alerts.httpx, "AsyncClient", return_value=ctx):
        ok = await alerts.send_alert_email("a@b.com", "subj", "body")

    assert ok is True
    kwargs = client.post.await_args.kwargs
    assert client.post.await_args.args[0] == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test"
    assert kwargs["json"]["to"] == ["a@b.com"]
    assert kwargs["json"]["text"] == "body"
    assert "html" not in kwargs["json"]


@pytest.mark.asyncio
async def test_send_alert_email_error_goes_to_sentry_and_returns_false():
    import mailer.alerts as alerts
    ctx, _ = _mock_async_client(SimpleNamespace(status_code=422, text="invalid from"))
    with patch.object(alerts, "RESEND_API_KEY", "re_test"), \
         patch.object(alerts.httpx, "AsyncClient", return_value=ctx), \
         patch.object(alerts.sentry_sdk, "capture_message") as capture:
        ok = await alerts.send_alert_email("a@b.com", "subj", "body")

    assert ok is False
    capture.assert_called_once()          # Resend error is reported to Sentry


@pytest.mark.asyncio
async def test_send_alert_email_network_failure_captured_not_raised():
    import mailer.alerts as alerts
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("boom"))
    ctx.__aexit__ = AsyncMock(return_value=False)
    with patch.object(alerts, "RESEND_API_KEY", "re_test"), \
         patch.object(alerts.httpx, "AsyncClient", return_value=ctx), \
         patch.object(alerts.sentry_sdk, "capture_exception") as capture:
        ok = await alerts.send_alert_email("a@b.com", "subj", "body")

    assert ok is False                    # never raises into the scan
    capture.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_email_without_key_returns_false():
    import mailer.alerts as alerts
    with patch.object(alerts, "RESEND_API_KEY", ""):
        assert await alerts.send_alert_email("a@b.com", "subj", "body") is False


# ---------------------------------------------------------------------------
# generate_weekly_review
# ---------------------------------------------------------------------------

class _FakeReviewDB:
    """Async session stub returning canned journal rows from execute()."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *args, **kwargs):
        return SimpleNamespace(all=lambda: self._rows)


def _trade_row(ticker="NVDA", strat="momentum", outcome="win", pnl=10.0):
    return SimpleNamespace(
        ticker=ticker, strategy_type=strat, outcome=outcome, outcome_pnl_pct=pnl
    )


def _no_review_cache():
    return (
        patch("agents.journal_agent.cache_configured", return_value=True),
        patch("agents.journal_agent.cache_get_json", new=AsyncMock(return_value=None)),
        patch("agents.journal_agent.cache_set_json", new=AsyncMock(return_value=True)),
    )


@pytest.mark.asyncio
async def test_weekly_review_skips_claude_under_three_trades():
    conf_p, get_p, set_p = _no_review_cache()
    db = _FakeReviewDB([_trade_row(), _trade_row(outcome="loss", pnl=-4.0)])  # only 2
    with conf_p, get_p, set_p as set_mock, patch("agents.journal_agent._call_claude") as claude:
        result = await generate_weekly_review(uuid.uuid4(), db)  # type: ignore[arg-type]

    assert result == EMPTY_REVIEW
    claude.assert_not_called()
    # The empty result is negative-cached briefly so page views can't hammer the DB
    assert set_mock.await_args.kwargs["ttl_seconds"] == 3600


@pytest.mark.asyncio
async def test_weekly_review_generates_and_caches():
    review = {
        "headline": "Momentum carried the week.",
        "bullets": ["a", "b", "c"],
        "generated_at": "2026-07-06",
    }
    conf_p, get_p, set_p = _no_review_cache()
    db = _FakeReviewDB([_trade_row(), _trade_row(), _trade_row(outcome="loss", pnl=-3.0)])
    with conf_p, get_p, set_p as set_mock, patch(
        "agents.journal_agent._call_claude",
        new=AsyncMock(return_value=(json.dumps(review), 200, 100)),
    ) as claude:
        result = await generate_weekly_review(uuid.uuid4(), db)  # type: ignore[arg-type]

    assert result == review
    # Called with the weekly-review model, and cached for 7 days
    assert claude.await_args.kwargs["model"] == "claude-sonnet-4-6"
    set_mock.assert_awaited_once()
    assert set_mock.await_args.args[0].startswith("weekly_review:")
    assert set_mock.await_args.kwargs["ttl_seconds"] == 604800


@pytest.mark.asyncio
async def test_weekly_review_returns_cached_without_db_or_claude():
    cached = {"headline": "Cached.", "bullets": [], "generated_at": "2026-07-05"}
    with patch("agents.journal_agent.cache_configured", return_value=True), patch(
        "agents.journal_agent.cache_get_json", new=AsyncMock(return_value=cached)
    ), patch("agents.journal_agent._call_claude") as claude:
        result = await generate_weekly_review(uuid.uuid4(), None)  # type: ignore[arg-type]

    assert result == cached
    claude.assert_not_called()


@pytest.mark.asyncio
async def test_weekly_review_refuses_claude_when_cache_unavailable():
    # No cache means no dedupe — every request would be a paid generation, so
    # the agent must not call Claude (or even the DB) at all.
    with patch("agents.journal_agent.cache_configured", return_value=False), patch(
        "agents.journal_agent._call_claude"
    ) as claude:
        result = await generate_weekly_review(uuid.uuid4(), None)  # type: ignore[arg-type]

    assert result == EMPTY_REVIEW
    claude.assert_not_called()


@pytest.mark.asyncio
async def test_weekly_review_negative_caches_parse_failure():
    conf_p, get_p, set_p = _no_review_cache()
    db = _FakeReviewDB([_trade_row(), _trade_row(), _trade_row()])
    with conf_p, get_p, set_p as set_mock, patch(
        "agents.journal_agent._call_claude",
        new=AsyncMock(return_value=("this is not json", 200, 100)),
    ) as claude:
        result = await generate_weekly_review(uuid.uuid4(), db)  # type: ignore[arg-type]

    assert result == EMPTY_REVIEW
    claude.assert_awaited_once()  # exactly one paid attempt
    # Failure cached with the short TTL — retries are bounded to ~hourly
    set_mock.assert_awaited_once()
    assert set_mock.await_args.kwargs["ttl_seconds"] == 3600

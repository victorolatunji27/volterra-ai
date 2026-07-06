# Integration tests for API routes — scans, journal, and user endpoints.
#
# These exercise FastAPI validation paths that reject requests BEFORE any
# database access, so no live Postgres is required. Auth-protected routes are
# tested via dependency override with a fake user.
import os
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENABLE_SCHEDULER", "false")

from api.deps import get_current_user  # noqa: E402
from db.database import get_db  # noqa: E402
from main import app  # noqa: E402


def _fake_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.tier = "free"
    user.strategy_tags = []
    user.created_at = datetime.now(tz=timezone.utc)
    return user


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authed_client(client):
    app.dependency_overrides[get_current_user] = _fake_user
    # Validation-only tests never reach the DB, but the route signature
    # still resolves the dependency — give it an inert mock.
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return client


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    """Stand-in for a SQLAlchemy Result with pre-baked return values."""

    def __init__(self, *, scalar_one=None, scalar_one_or_none=None, one=None, first=None, all=None):
        self._scalar_one = scalar_one
        self._scalar_one_or_none = scalar_one_or_none
        self._one = one
        self._first = first
        self._all = all or []

    def scalar_one(self):
        return self._scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def one(self):
        return self._one

    def first(self):
        return self._first

    def all(self):
        return self._all

    def scalars(self):
        return _FakeScalars(self._all)


class _FakeSession:
    """Async session that returns queued _FakeResults in order from execute()."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, *args, **kwargs):
        return self._results.pop(0)


def _db_returning(*results):
    return lambda: _FakeSession(results)


@pytest.fixture
def no_analytics_cache():
    """Force the analytics cache to always miss and swallow writes (no network)."""
    with patch(
        "api.routes.analytics.cache_get_json", new=AsyncMock(return_value=None)
    ), patch(
        "api.routes.analytics.cache_set_json", new=AsyncMock(return_value=False)
    ):
        yield


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_journal_requires_auth(client):
    response = client.get("/api/journal")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_create_journal_invalid_ticker_returns_422(authed_client):
    response = authed_client.post("/api/journal", json={"ticker": "TOOLONG123"})
    assert response.status_code == 422


def test_create_journal_lowercase_short_ticker_is_normalised(authed_client):
    # "aapl" is valid after strip/uppercase — it must pass schema validation.
    # (It will fail later at the DB layer in this test setup, which is fine:
    # we only assert it is NOT a 422.)
    response = authed_client.post("/api/journal", json={"ticker": "aapl"})
    assert response.status_code != 422


def test_create_journal_long_notes_returns_422(authed_client):
    response = authed_client.post(
        "/api/journal", json={"ticker": "AAPL", "user_notes": "x" * 2001}
    )
    assert response.status_code == 422


def test_create_journal_bad_entry_price_returns_422(authed_client):
    response = authed_client.post(
        "/api/journal", json={"ticker": "AAPL", "entry_price": -5}
    )
    assert response.status_code == 422


def test_create_journal_bad_strategy_type_returns_422(authed_client):
    response = authed_client.post(
        "/api/journal", json={"ticker": "AAPL", "strategy_type": "yolo"}
    )
    assert response.status_code == 422


def test_update_outcome_invalid_value_returns_422(authed_client):
    response = authed_client.patch(
        "/api/journal/1/outcome", json={"outcome": "moon"}
    )
    assert response.status_code == 422


def test_scans_invalid_ticker_returns_400(client):
    response = client.get("/api/scans/TOOLONGTICKER")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid ticker symbol"


def test_scans_days_above_max_returns_422(authed_client):
    response = authed_client.get("/api/scans/AAPL", params={"days": 31})
    assert response.status_code == 422


def test_test_alert_requires_pro_tier(authed_client):
    response = authed_client.post("/api/users/me/test-alert")
    assert response.status_code == 403


def test_update_strategies_rejects_invalid_tags(authed_client):
    response = authed_client.patch(
        "/api/users/me/strategies", json={"strategy_tags": ["momentum", "bogus"]}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Analytics routes
# ---------------------------------------------------------------------------

def test_analytics_summary_requires_auth(client):
    response = client.get("/api/analytics/summary")
    assert response.status_code == 401


def test_analytics_summary_empty_state_is_zeroed(client, no_analytics_cache):
    app.dependency_overrides[get_current_user] = _fake_user
    # 1st execute: total count → 0. 2nd: resolved aggregate → resolved=0.
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(scalar_one=0),
        _FakeResult(one=SimpleNamespace(resolved=0, wins=None, avg_pnl=None)),
    )
    body = client.get("/api/analytics/summary").json()
    assert body == {
        "total_trades": 0,
        "resolved_trades": 0,
        "win_rate": 0.0,
        "avg_pnl_pct": 0.0,
        "best_setup": None,
        "worst_setup": None,
    }


def test_analytics_summary_computes_stats(client, no_analytics_cache):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(scalar_one=4),                                             # total_trades
        _FakeResult(one=SimpleNamespace(resolved=3, wins=2, avg_pnl=5.0)),     # aggregates
        _FakeResult(first=SimpleNamespace(ticker="NVDA", outcome_pnl_pct=12.0)),  # best
        _FakeResult(first=SimpleNamespace(ticker="META", outcome_pnl_pct=-4.0)),  # worst
    )
    body = client.get("/api/analytics/summary").json()
    assert body["total_trades"] == 4
    assert body["resolved_trades"] == 3
    assert body["win_rate"] == 66.7           # 2/3
    assert body["avg_pnl_pct"] == 5.0
    assert body["best_setup"] == {"ticker": "NVDA", "pnl_pct": 12.0}
    assert body["worst_setup"] == {"ticker": "META", "pnl_pct": -4.0}


def test_analytics_by_strategy_empty_is_empty_list(client, no_analytics_cache):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _db_returning(_FakeResult(all=[]))
    assert client.get("/api/analytics/by-strategy").json() == []


def test_analytics_by_ticker_ranks_and_computes_win_rate(client, no_analytics_cache):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(all=[
            SimpleNamespace(ticker="NVDA", trade_count=4, wins=3),
            SimpleNamespace(ticker="META", trade_count=2, wins=1),
        ])
    )
    body = client.get("/api/analytics/by-ticker").json()
    assert body == [
        {"ticker": "NVDA", "trade_count": 4, "win_rate": 75.0},
        {"ticker": "META", "trade_count": 2, "win_rate": 50.0},
    ]


def test_analytics_equity_curve_accumulates(client, no_analytics_cache):
    app.dependency_overrides[get_current_user] = _fake_user
    d1 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    d2 = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(all=[
            SimpleNamespace(resolved_at=d1, outcome_pnl_pct=5.0),
            SimpleNamespace(resolved_at=d2, outcome_pnl_pct=-2.0),
        ])
    )
    body = client.get("/api/analytics/equity-curve").json()
    assert body == [
        {"date": "2026-06-01", "cumulative_pnl_pct": 5.0},
        {"date": "2026-06-03", "cumulative_pnl_pct": 3.0},
    ]


# ---------------------------------------------------------------------------
# Ticker detail route
# ---------------------------------------------------------------------------

def _fake_scan() -> SimpleNamespace:
    return SimpleNamespace(
        id=1, ticker="NVDA", scan_date=date(2026, 6, 10),
        call_volume=45000, put_volume=8000, oi_ratio=4.2,
        call_put_ratio=None, avg_strike=520.0, avg_expiry=None,
        iv_rank=68.0, price_at_scan=498.0,
        created_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        summary=None, raw_data={"call_put_ratio": 5.6},
    )


def _fake_summary() -> SimpleNamespace:
    return SimpleNamespace(
        id=7, setup_summary="Heavy calls", flow_interpretation="Bullish",
        risk_note="IV elevated", strategy_tags=["momentum"],
        created_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        news_used={"catalyst_note": "earnings", "contradiction_note": "macro"},
    )


def test_ticker_requires_auth(client):
    assert client.get("/api/ticker/NVDA").status_code == 401


def test_ticker_invalid_symbol_returns_400(authed_client):
    response = authed_client.get("/api/ticker/TOOLONGTICKER")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid ticker symbol"


def test_ticker_unknown_symbol_returns_404(client):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(scalar_one_or_none=None)  # no latest scan for this symbol
    )
    response = client.get("/api/ticker/ZZZZ")
    assert response.status_code == 404
    assert response.json()["detail"] == "No data for ZZZZ"


def test_ticker_detail_success(client):
    app.dependency_overrides[get_current_user] = _fake_user
    scan = _fake_scan()
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(scalar_one_or_none=scan),            # latest scan
        _FakeResult(scalar_one_or_none=_fake_summary()),  # latest summary
        _FakeResult(all=[scan]),                          # history rows
    )
    series = [{"date": "2026-06-01", "close": 100.0}, {"date": "2026-06-02", "close": 102.5}]
    with patch("api.routes.ticker.get_price_history", new=AsyncMock(return_value=series)):
        body = client.get("/api/ticker/nvda").json()

    assert body["symbol"] == "NVDA"                       # normalised to uppercase
    assert body["latest"]["ticker"] == "NVDA"
    assert body["latest"]["call_put_ratio"] == 5.6        # pulled from raw_data
    assert body["latest"]["summary"]["setup_summary"] == "Heavy calls"
    assert body["news"] == {"catalyst_note": "earnings", "contradiction_note": "macro"}
    assert body["history"] == [{
        "scan_date": "2026-06-10", "oi_ratio": 4.2, "call_put_ratio": 5.6,
        "iv_rank": 68.0, "price_at_scan": 498.0,
    }]
    assert body["price_series"] == series


def test_ticker_detail_degrades_when_price_history_fails(client):
    app.dependency_overrides[get_current_user] = _fake_user
    scan = _fake_scan()
    app.dependency_overrides[get_db] = _db_returning(
        _FakeResult(scalar_one_or_none=scan),
        _FakeResult(scalar_one_or_none=_fake_summary()),
        _FakeResult(all=[scan]),
    )
    # yfinance failure → get_price_history returns None; request must still succeed.
    with patch("api.routes.ticker.get_price_history", new=AsyncMock(return_value=None)):
        response = client.get("/api/ticker/NVDA")

    assert response.status_code == 200
    body = response.json()
    assert body["price_series"] is None
    assert body["latest"]["ticker"] == "NVDA"
    assert len(body["history"]) == 1

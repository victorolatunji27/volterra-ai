# Integration tests for API routes — scans, journal, and user endpoints.
#
# These exercise FastAPI validation paths that reject requests BEFORE any
# database access, so no live Postgres is required. Auth-protected routes are
# tested via dependency override with a fake user.
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

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

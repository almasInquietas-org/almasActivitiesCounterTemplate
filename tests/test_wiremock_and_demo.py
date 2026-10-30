"""
Unit and integration tests for WireMock stubs and demo scripts.
"""
import json
import os
import subprocess
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from api import api_config as config
from api import db


# ---------------------------------------------------------------------------
# Tests for WireMock JSON Mapping Files
# ---------------------------------------------------------------------------

def test_wiremock_compose_file_exists():
    compose_path = os.path.join("mocks", "docker-compose.yml")
    assert os.path.exists(compose_path), "mocks/docker-compose.yml must exist"
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "wiremock" in content.lower()
    assert "8089" in content


def test_wiremock_mappings_valid_json():
    auth_mapping_path = os.path.join("mocks", "wiremock", "mappings", "oauth-authorize.json")
    token_mapping_path = os.path.join("mocks", "wiremock", "mappings", "oauth-token.json")

    assert os.path.exists(auth_mapping_path), f"{auth_mapping_path} must exist"
    assert os.path.exists(token_mapping_path), f"{token_mapping_path} must exist"

    # Verify oauth-authorize.json
    with open(auth_mapping_path, "r", encoding="utf-8") as f:
        auth_data = json.load(f)
    assert auth_data.get("request", {}).get("method") == "GET"
    assert auth_data.get("request", {}).get("urlPath") == "/oauth/authorize"
    assert auth_data.get("response", {}).get("status") == 302
    location_header = auth_data.get("response", {}).get("headers", {}).get("Location", "")
    assert "redirect_uri" in location_header or "{{request.query.redirect_uri}}" in location_header
    assert "code=" in location_header

    # Verify oauth-token.json
    with open(token_mapping_path, "r", encoding="utf-8") as f:
        token_data = json.load(f)

    # Could be a single mapping with mappings array or mapping file with list/dict
    mappings = token_data.get("mappings") if isinstance(token_data, dict) and "mappings" in token_data else [token_data]
    assert len(mappings) >= 2, "Must contain at least success and failure token stubs"

    statuses = [m.get("response", {}).get("status") for m in mappings]
    assert 200 in statuses, "Must contain 200 OK stub"
    assert 400 in statuses, "Must contain 400 Bad Request stub"


# ---------------------------------------------------------------------------
# Tests for scripts/seed_demo_data.py
# ---------------------------------------------------------------------------

def test_seed_demo_data_prod_safety_guard(monkeypatch):
    """Safety guard: seed_demo_data must refuse to run if table ends with _PROD."""
    from scripts import seed_demo_data

    monkeypatch.setattr(seed_demo_data, "ATHLETES_TABLE_NAME", "ATHLETES_PROD")
    with pytest.raises(SystemExit) as exc_info:
        seed_demo_data.seed(env="prod", reset=True)
    assert exc_info.value.code != 0


def test_seed_demo_data_populates_dev(dynamodb_mock, monkeypatch):
    """Running seed_demo_data against DEV populates athletes and activities."""
    from scripts import seed_demo_data

    # Use DEV tables initialized by dynamodb_mock
    monkeypatch.setenv("ATHLETES_TABLE_NAME", "ATHLETES_DEV")
    monkeypatch.setenv("ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")
    monkeypatch.setattr(config, "ATHLETES_TABLE_NAME", "ATHLETES_DEV")
    monkeypatch.setattr(config, "ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")

    # Run seeder with reset
    result = seed_demo_data.seed(env="dev", reset=True, club="almas_inquietas")

    assert result["athletes_count"] >= 12
    assert result["activities_count"] >= 40

    # Verify DB content
    activities = db.get_all_activities()
    assert len(activities) >= 40

    # Verify sport types variety
    types = {a.get("type") for a in activities}
    assert {"Run", "Ride"}.issubset(types)

    # Verify athlete lookup
    ath = db.get_athlete("i_demo_01")
    assert ath is not None
    assert "almas_inquietas" in ath.get("clubs", [])


def test_seed_demo_data_reset_clears_old(dynamodb_mock, monkeypatch):
    """Verify --reset flag wipes existing records before seeding."""
    from scripts import seed_demo_data

    monkeypatch.setenv("ATHLETES_TABLE_NAME", "ATHLETES_DEV")
    monkeypatch.setenv("ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")
    monkeypatch.setattr(config, "ATHLETES_TABLE_NAME", "ATHLETES_DEV")
    monkeypatch.setattr(config, "ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")

    # First seed
    seed_demo_data.seed(env="dev", reset=True)
    count_1 = len(db.get_all_activities())

    # Second seed with reset should restore clean state without ballooning count
    seed_demo_data.seed(env="dev", reset=True)
    count_2 = len(db.get_all_activities())
    assert count_1 == count_2


# ---------------------------------------------------------------------------
# Tests for scripts/simulate_webhook.py
# ---------------------------------------------------------------------------

def test_simulate_webhook_sends_valid_payload():
    """Simulate webhook constructs proper JSON and sends POST."""
    from scripts import simulate_webhook

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"status": "ok", "processed": 1, "saved": 1}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        status, body = simulate_webhook.send_webhook(
            url="http://127.0.0.1:5000",
            secret="dev-webhook-secret",
            athlete_id="i_demo_01",
            activity_title="Live Demo Ride",
            act_type="Ride",
            km=25.4,
        )

        assert status == 200
        assert body.get("status") == "ok"
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://127.0.0.1:5000/webhook"
        assert req.method == "POST"

        payload = json.loads(req.data.decode("utf-8"))
        assert payload["secret"] == "dev-webhook-secret"
        events = payload["events"]
        assert len(events) == 1
        assert events[0]["athlete_id"] == "i_demo_01"
        assert events[0]["activity"]["name"] == "Live Demo Ride"
        assert events[0]["activity"]["distance"] == 25400
        assert events[0]["activity"]["type"] == "Ride"


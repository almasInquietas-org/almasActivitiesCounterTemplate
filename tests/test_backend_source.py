import base64
import json
import pytest
from unittest.mock import patch
from api import api_config as config
from api.intervals_oauth import OAuthError


def make_v1_event(http_method="GET", path="/", query_params=None, headers=None, body=None, source_ip="127.0.0.1", is_base64=False):
    return {
        "httpMethod": http_method,
        "path": path,
        "queryStringParameters": query_params or {},
        "headers": headers or {},
        "body": body or "",
        "isBase64Encoded": is_base64,
        "requestContext": {
            "identity": {
                "sourceIp": source_ip
            }
        }
    }


def make_v2_event(method="GET", raw_path="/", query_params=None, headers=None, body=None, source_ip="127.0.0.1", is_base64=False):
    return {
        "rawPath": raw_path,
        "queryStringParameters": query_params or {},
        "headers": headers or {},
        "body": body or "",
        "isBase64Encoded": is_base64,
        "requestContext": {
            "http": {
                "method": method,
                "path": raw_path,
                "sourceIp": source_ip
            }
        }
    }


def test_parse_event_v1():
    from api.backend_source import _parse_event
    event = make_v1_event(
        http_method="GET",
        path="/oauth/callback",
        query_params={"code": "auth123", "state": "club_test"},
        headers={"Host": "api.example.com", "X-Custom": "val"},
        source_ip="192.168.1.10",
    )
    parsed = _parse_event(event)
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/oauth/callback"
    assert parsed["query_params"] == {"code": "auth123", "state": "club_test"}
    assert parsed["headers"]["host"] == "api.example.com"
    assert parsed["headers"]["x-custom"] == "val"
    assert parsed["client_ip"] == "192.168.1.10"
    assert parsed["body"] == ""


def test_parse_event_v2_and_base64():
    from api.backend_source import _parse_event
    encoded_body = base64.b64encode(b"hello world").decode("utf-8")
    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        query_params={"test": "1"},
        headers={"Content-Type": "application/json"},
        body=encoded_body,
        source_ip="10.0.0.5",
        is_base64=True,
    )
    parsed = _parse_event(event)
    assert parsed["method"] == "POST"
    assert parsed["path"] == "/webhook"
    assert parsed["query_params"] == {"test": "1"}
    assert parsed["headers"]["content-type"] == "application/json"
    assert parsed["client_ip"] == "10.0.0.5"
    assert parsed["body"] == "hello world"


def test_oauth_callback_success(dynamodb_mock):
    from api.backend_source import process_activities
    from api.db import get_athlete

    event = make_v2_event(
        method="GET",
        raw_path="/oauth/callback",
        query_params={"code": "mock_code_123", "state": "test_club"}
    )

    with patch("api.backend_source.intervals_oauth.exchange_code_for_token") as mock_exchange:
        mock_exchange.return_value = {
            "access_token": "token_abc_xyz",
            "athlete_id": "i99999",
            "athlete_name": "Test Athlete"
        }
        response = process_activities(event, None)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "Registration Successful" in response["body"]
    assert "Test Athlete" in response["body"]
    assert "test_club" in response["body"]

    # Verify athlete was saved in DynamoDB
    athlete = get_athlete("i99999")
    assert athlete is not None
    assert athlete["athlete_id"] == "i99999"
    assert athlete["athlete_name"] == "Test Athlete"
    assert athlete["access_token"] == "token_abc_xyz"
    assert athlete["clubs"] == ["test_club"]


def test_oauth_callback_default_club(dynamodb_mock):
    from api.backend_source import process_activities
    from api.db import get_athlete

    # state missing -> defaults to 'default'
    event = make_v1_event(
        http_method="GET",
        path="/oauth/callback",
        query_params={"code": "mock_code_456"}
    )

    with patch("api.backend_source.intervals_oauth.exchange_code_for_token") as mock_exchange:
        mock_exchange.return_value = {
            "access_token": "token_default_club",
            "athlete_id": "i88888",
            "athlete_name": "Default Club Runner"
        }
        response = process_activities(event, None)

    assert response["statusCode"] == 200
    assert "Registration Successful" in response["body"]
    assert "Default Club Runner" in response["body"]
    assert "default" in response["body"]

    athlete = get_athlete("i88888")
    assert athlete is not None
    assert athlete["clubs"] == ["default"]


def test_oauth_callback_missing_code():
    from api.backend_source import process_activities

    event = make_v2_event(
        method="GET",
        raw_path="/oauth/callback",
        query_params={"state": "some_club"}
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 400
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "Could Not Connect" in response["body"] or "Registration Failed" in response["body"]
    assert "Missing authorization code" in response["body"]


def test_oauth_callback_access_denied():
    from api.backend_source import process_activities

    event = make_v2_event(
        method="GET",
        raw_path="/oauth/callback",
        query_params={"error": "access_denied", "state": "some_club"}
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 400
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "Access was denied" in response["body"]


def test_oauth_callback_token_exchange_error():
    from api.backend_source import process_activities

    event = make_v2_event(
        method="GET",
        raw_path="/oauth/callback",
        query_params={"code": "bad_code", "state": "some_club"}
    )

    with patch("api.backend_source.intervals_oauth.exchange_code_for_token") as mock_exchange:
        mock_exchange.side_effect = OAuthError("Upstream Intervals.icu 400 Bad Request")
        response = process_activities(event, None)

    assert response["statusCode"] == 400
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert "Registration Failed" in response["body"] or "Could Not Connect" in response["body"]
    assert "Upstream Intervals.icu 400 Bad Request" in response["body"]


# --- Story 6: POST /webhook & Flow Tests ---

def test_webhook_invalid_secret(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "super-secret-123")

    payload = {
        "secret": "wrong-secret",
        "events": []
    }
    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps(payload),
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 401
    data = json.loads(response["body"])
    assert data.get("error") == "Unauthorized"


def test_webhook_empty_secret_unauthorized(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    # If INTERVALS_WEBHOOK_SECRET is empty string or unset, all requests should be 401
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "")

    payload = {
        "secret": "",
        "events": []
    }
    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps(payload),
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 401


def test_webhook_malformed_json():
    from api.backend_source import process_activities

    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body="not-a-valid-json{{{",
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 400
    data = json.loads(response["body"])
    assert "Malformed JSON" in data.get("error", "")


def test_webhook_valid_ingestion(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    from api.db import save_athlete, get_all_activities
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "test-secret")

    # Pre-register athlete
    save_athlete("i2049151", "Daniel Fernandez", "tok_xyz", "almas_inquietas")

    payload = {
        "secret": "test-secret",
        "events": [
            {
                "athlete_id": "i2049151",
                "type": "ACTIVITY_UPLOADED",
                "timestamp": "2026-10-24T06:40:47.011+00:00",
                "activity": {
                    "id": 48566307,
                    "start_date_local": "2026-10-24T06:30:00",
                    "type": "Ride",
                    "name": "Morning Ride",
                    "moving_time": 3600,
                    "distance": 30000,
                    "total_elevation_gain": 250
                }
            }
        ]
    }

    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps(payload),
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["status"] == "ok"
    assert data["processed"] == 1
    assert data["saved"] == 1

    # Verify activity stored in DynamoDB
    activities = get_all_activities()
    assert len(activities) == 1
    act = activities[0]
    assert act["activity_id"] == "48566307"
    assert act["athlete_id"] == "i2049151"
    assert act["athlete"] == "Daniel Fernandez"
    assert act["clubs"] == ["almas_inquietas"]
    assert float(act["distance_km"]) == 30.0


def test_webhook_idempotency_duplicate_activity(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    from api.db import save_athlete, get_all_activities
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "test-secret")

    save_athlete("i2049151", "Daniel Fernandez", "tok_xyz", "almas_inquietas")

    payload = {
        "secret": "test-secret",
        "events": [
            {
                "athlete_id": "i2049151",
                "type": "ACTIVITY_UPLOADED",
                "activity": {
                    "id": 48566307,
                    "distance": 10000,
                    "name": "Run",
                    "type": "Run",
                }
            }
        ]
    }
    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps(payload),
    )

    # First attempt: processed=1, saved=1
    res1 = process_activities(event, None)
    assert res1["statusCode"] == 200
    data1 = json.loads(res1["body"])
    assert data1["processed"] == 1
    assert data1["saved"] == 1

    # Second attempt: processed=1, saved=0 (idempotent, ConditionalCheckFailedException caught)
    res2 = process_activities(event, None)
    assert res2["statusCode"] == 200
    data2 = json.loads(res2["body"])
    assert data2["processed"] == 1
    assert data2["saved"] == 0

    assert len(get_all_activities()) == 1


def test_webhook_unknown_athlete_and_non_activity_event(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    from api.db import save_athlete, get_all_activities
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "test-secret")

    save_athlete("i100", "Known Athlete", "tok", "club1")

    payload = {
        "secret": "test-secret",
        "events": [
            # 1. Non-ACTIVITY_UPLOADED event (e.g. ATHLETE_UPDATED) -> ignored
            {
                "athlete_id": "i100",
                "type": "ATHLETE_UPDATED",
                "activity": {"id": 111}
            },
            # 2. Unknown athlete -> skipped gracefully
            {
                "athlete_id": "i_unknown_999",
                "type": "ACTIVITY_UPLOADED",
                "activity": {"id": 222, "name": "Secret Run", "distance": 5000}
            },
            # 3. Known athlete -> processed & saved
            {
                "athlete_id": "i100",
                "type": "ACTIVITY_UPLOADED",
                "activity": {"id": 333, "name": "Known Run", "distance": 5000}
            }
        ]
    }

    event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps(payload),
    )
    response = process_activities(event, None)
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["processed"] == 2  # Only the 2 ACTIVITY_UPLOADED events counted in processed
    assert data["saved"] == 1      # Only the known athlete saved

    activities = get_all_activities()
    assert len(activities) == 1
    assert activities[0]["activity_id"] == "333"


def test_e2e_flow_callback_webhook_and_dashboard(dynamodb_mock, monkeypatch):
    """
    E2E flow test:
    1. OAuth callback registers athlete Daniel in club 'ciclistas_valencia'
    2. Webhook arrives with a 45.5 km ride for Daniel
    3. GET / returns dashboard data reflecting the ride
    """
    from api.backend_source import process_activities
    monkeypatch.setattr(config, "INTERVALS_WEBHOOK_SECRET", "webhook-sec")
    # Passthrough auth for GET / to verify dashboard aggregation
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "API_SIGNING_SECRET", "")

    # Step 1: OAuth Callback
    cb_event = make_v2_event(
        method="GET",
        raw_path="/oauth/callback",
        query_params={"code": "auth_code_789", "state": "ciclistas_valencia"}
    )
    with patch("api.backend_source.intervals_oauth.exchange_code_for_token") as mock_exchange:
        mock_exchange.return_value = {
            "access_token": "token_valencia",
            "athlete_id": "i777",
            "athlete_name": "Daniel F."
        }
        cb_res = process_activities(cb_event, None)
    assert cb_res["statusCode"] == 200

    # Step 2: Webhook receiver
    webhook_event = make_v2_event(
        method="POST",
        raw_path="/webhook",
        body=json.dumps({
            "secret": "webhook-sec",
            "events": [
                {
                    "athlete_id": "i777",
                    "type": "ACTIVITY_UPLOADED",
                    "activity": {
                        "id": 998877,
                        "name": "Gran Fondo",
                        "type": "Ride",
                        "distance": 45500,
                        "start_date_local": "2026-10-25T08:00:00"
                    }
                }
            ]
        })
    )
    wh_res = process_activities(webhook_event, None)
    assert wh_res["statusCode"] == 200
    wh_data = json.loads(wh_res["body"])
    assert wh_data["processed"] == 1
    assert wh_data["saved"] == 1

    # Step 3: GET / (Dashboard route)
    dash_event = make_v2_event(method="GET", raw_path="/")
    dash_res = process_activities(dash_event, None)
    assert dash_res["statusCode"] == 200
    dash_data = json.loads(dash_res["body"])
    assert dash_data["total_km"] == 45.5
    assert dash_data["total_activities"] == 1
    assert len(dash_data["top_athletes"]) == 1
    assert dash_data["top_athletes"][0]["athlete_name"] == "Daniel F."
    assert dash_data["top_athletes"][0]["currentKm"] == 45.5


def test_options_cors_preflight():
    from api.backend_source import process_activities
    event = make_v2_event(method="OPTIONS", raw_path="/")
    res = process_activities(event, None)
    assert res["statusCode"] == 204
    assert res["headers"]["Access-Control-Allow-Methods"] == "GET,POST,OPTIONS"


def test_auth_token_and_protected_dashboard(dynamodb_mock, monkeypatch):
    import time
    import hmac
    import hashlib
    from api.backend_source import process_activities
    from api import api_config as cfg

    monkeypatch.setattr(cfg, "API_KEY", "secret-api-key")
    monkeypatch.setattr(cfg, "API_SIGNING_SECRET", "secret-signing-key")
    monkeypatch.setattr(cfg, "AUTH_TOLERANCE_SECONDS", 300)
    monkeypatch.setattr(cfg, "TOKEN_TTL_SECONDS", 300)

    # 1. Invalid signature on /auth/token
    bad_auth_event = make_v2_event(
        method="POST",
        raw_path="/auth/token",
        headers={"x-api-key": "secret-api-key", "x-signature": "wrong"}
    )
    res_bad = process_activities(bad_auth_event, None)
    assert res_bad["statusCode"] == 401

    # 2. Valid signature on /auth/token
    now_ts = str(time.time())
    nonce = "test-nonce-123"
    msg = f"{now_ts}.{nonce}".encode("utf-8")
    valid_sig = hmac.new(b"secret-signing-key", msg, hashlib.sha256).hexdigest()

    good_auth_event = make_v2_event(
        method="POST",
        raw_path="/auth/token",
        headers={
            "x-api-key": "secret-api-key",
            "x-timestamp": now_ts,
            "x-nonce": nonce,
            "x-signature": valid_sig,
        }
    )
    res_token = process_activities(good_auth_event, None)
    assert res_token["statusCode"] == 200
    token_body = json.loads(res_token["body"])
    token = token_body["token"]

    # 3. Request GET / without token -> 401
    unauth_dash = make_v2_event(method="GET", raw_path="/")
    res_unauth = process_activities(unauth_dash, None)
    assert res_unauth["statusCode"] == 401

    # 4. Request GET / with valid Bearer token -> 200
    auth_dash = make_v2_event(
        method="GET",
        raw_path="/",
        headers={"authorization": f"Bearer {token}"}
    )
    res_auth = process_activities(auth_dash, None)
    assert res_auth["statusCode"] == 200


def test_rate_limiting_route(dynamodb_mock, monkeypatch):
    from api.backend_source import process_activities
    from api import api_config as cfg

    monkeypatch.setattr(cfg, "RATE_LIMIT_MAX", 2)
    monkeypatch.setattr(cfg, "RATE_LIMIT_WINDOW", 60)

    event = make_v2_event(method="GET", raw_path="/", source_ip="203.0.113.1")
    assert process_activities(event, None)["statusCode"] == 200
    assert process_activities(event, None)["statusCode"] == 200
    assert process_activities(event, None)["statusCode"] == 429


def test_not_found_route():
    from api.backend_source import process_activities
    event = make_v2_event(method="GET", raw_path="/nonexistent")
    res = process_activities(event, None)
    assert res["statusCode"] == 404



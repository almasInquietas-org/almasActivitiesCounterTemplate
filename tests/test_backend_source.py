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

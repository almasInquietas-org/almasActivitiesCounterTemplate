"""
tests/test_intervals_oauth.py - Unit tests for api/intervals_oauth.py
"""
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from api import api_config as config
from api.intervals_oauth import OAuthError, exchange_code_for_token, render_callback_html


def test_exchange_code_for_token_success(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "http://localhost:8089")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_SECRET", "test-client-secret")

    mock_response_body = {
        "token_type": "Bearer",
        "access_token": "mock-access-token-12345",
        "scope": "ACTIVITY:READ",
        "athlete": {
            "id": "i2049151",
            "name": "Daniel Fernandez",
        },
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = exchange_code_for_token("test-code-123")

        assert result == {
            "access_token": "mock-access-token-12345",
            "athlete_id": "i2049151",
            "athlete_name": "Daniel Fernandez",
        }

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:8089/api/oauth/token"
        assert req.method == "POST"
        assert req.get_header("Content-type") == "application/x-www-form-urlencoded"
        data_str = req.data.decode("utf-8")
        assert "client_id=test-client-id" in data_str
        assert "client_secret=test-client-secret" in data_str
        assert "code=test-code-123" in data_str


def test_exchange_code_for_token_custom_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "https://custom.intervals.icu/")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_ID", "id")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_SECRET", "secret")

    mock_response_body = {
        "access_token": "tok",
        "athlete": {"id": "123", "name": "Athlete"},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        exchange_code_for_token("abc")
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://custom.intervals.icu/api/oauth/token"


def test_exchange_code_for_token_http_error(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "http://localhost:8089")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_ID", "id")
    monkeypatch.setattr(config, "INTERVALS_CLIENT_SECRET", "secret")

    error_response = io.BytesIO(b'{"error": "invalid_grant", "error_description": "Code expired"}')
    http_error = urllib.error.HTTPError(
        url="http://localhost:8089/api/oauth/token",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=error_response,
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(OAuthError) as exc_info:
            exchange_code_for_token("expired_code")
        assert "400" in str(exc_info.value)
        assert "invalid_grant" in str(exc_info.value)


def test_exchange_code_for_token_url_error(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "http://unreachable:8089")
    url_error = urllib.error.URLError("Connection refused")

    with patch("urllib.request.urlopen", side_effect=url_error):
        with pytest.raises(OAuthError) as exc_info:
            exchange_code_for_token("some_code")
        assert "Connection refused" in str(exc_info.value)


def test_exchange_code_for_token_invalid_json(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "http://localhost:8089")
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html>Not JSON</html>"
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(OAuthError) as exc_info:
            exchange_code_for_token("code123")
        assert "JSON" in str(exc_info.value) or "invalid" in str(exc_info.value).lower()


def test_exchange_code_for_token_missing_fields(monkeypatch):
    monkeypatch.setattr(config, "INTERVALS_OAUTH_BASE_URL", "http://localhost:8089")
    # Payload missing 'athlete'
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"access_token": "tok"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(OAuthError) as exc_info:
            exchange_code_for_token("code123")
        assert "athlete" in str(exc_info.value).lower()


def test_render_callback_html_success():
    html = render_callback_html(
        success=True,
        athlete_name="Daniel <script>alert(1)</script> Fernandez",
        club_id="club_&_more",
    )
    assert "<!DOCTYPE html>" in html
    assert "Daniel &lt;script&gt;alert(1)&lt;/script&gt; Fernandez" in html
    assert "club_&amp;_more" in html
    assert "<script>alert(1)</script>" not in html
    assert "Registration Successful" in html or "Registered" in html or "Welcome" in html
    assert "#0d9488" in html or "#14b8a6" in html or "teal" in html.lower()


def test_render_callback_html_error():
    html = render_callback_html(
        success=False,
        error_msg="Access denied: <b>invalid</b> token",
    )
    assert "<!DOCTYPE html>" in html
    assert "Registration Failed" in html or "Error" in html
    assert "Access denied: &lt;b&gt;invalid&lt;/b&gt; token" in html
    assert "<b>invalid</b>" not in html

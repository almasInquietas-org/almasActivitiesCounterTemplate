from dataclasses import FrozenInstanceError
import hashlib
import hmac
import logging
import time
import pytest
from api import api_config, auth, rate_limiter


def test_load_config_empty_env_uses_safe_defaults():
    cfg = api_config.load_config({})

    assert cfg.AWS_REGION == ""
    assert cfg.ATHLETES_TABLE_NAME == ""
    assert cfg.ACTIVITIES_TABLE_NAME == ""
    assert cfg.INTERVALS_OAUTH_BASE_URL == "https://intervals.icu"
    assert cfg.INTERVALS_CLIENT_ID == ""
    assert cfg.INTERVALS_CLIENT_SECRET == ""
    assert cfg.INTERVALS_WEBHOOK_SECRET == ""
    assert cfg.GOAL_KM is None
    assert cfg.LAST_ACT == 10
    assert cfg.TITLE == "Almas Inquietas Activities"
    assert cfg.CHECKPOINTS == ()
    assert cfg.ACT_TYPE_FILTER == ""
    assert cfg.ACT_TITLE_FILTER == ""
    assert cfg.START_DATE == ""
    assert cfg.CLUB_FILTER == ""
    assert cfg.API_KEY == ""
    assert cfg.API_SIGNING_SECRET == ""
    assert cfg.AUTH_TOLERANCE_SECONDS == 300
    assert cfg.TOKEN_TTL_SECONDS == 300
    assert cfg.RATE_LIMIT_MAX == 60
    assert cfg.RATE_LIMIT_WINDOW == 60
    assert cfg.CORS_ALLOWED_ORIGINS == ()


def test_empty_env_prevents_429_and_401_outage(monkeypatch):
    empty_cfg = api_config.load_config({})
    monkeypatch.setattr(api_config, "RATE_LIMIT_MAX", empty_cfg.RATE_LIMIT_MAX)
    monkeypatch.setattr(api_config, "RATE_LIMIT_WINDOW", empty_cfg.RATE_LIMIT_WINDOW)
    monkeypatch.setattr(api_config, "AUTH_TOLERANCE_SECONDS", empty_cfg.AUTH_TOLERANCE_SECONDS)
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", empty_cfg.TOKEN_TTL_SECONDS)

    # Must not return 429 on first request when rate-limit env vars are omitted
    assert rate_limiter.is_rate_limited("198.51.100.10") is False

    # Must not reject valid auth handshake or mint already-expired tokens
    monkeypatch.setattr(api_config, "API_KEY", "k1")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "s1")
    now_ts = str(time.time())
    nonce = "n-empty-env"
    sig = hmac.new(b"s1", f"{now_ts}.{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()

    assert auth.verify_signature("k1", now_ts, nonce, sig) is True
    token, ttl = auth.generate_token()
    assert ttl == 300
    assert auth.verify_token(token) is True


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("", None),
        ("   ", None),
        ("none", None),
        ("NONE", None),
        ("null", None),
        ("0", None),
        ("0.0", None),
        ("-50", None),
        ("NaN", None),
        ("inf", None),
        ("-inf", None),
        ("5,000", None),
        ("500", 500.0),
        ("1234.5", 1234.5),
    ],
)
def test_goal_km_parsing(raw_value, expected):
    cfg = api_config.load_config({"GOAL_KM": raw_value})
    assert cfg.GOAL_KM == expected


def test_malformed_numeric_env_vars_fallback_safely_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        cfg = api_config.load_config({
            "CHECKPOINTS": "100,bad,-5,nan,inf,250.5",
            "RATE_LIMIT_MAX": "abc",
            "RATE_LIMIT_WINDOW": "12.5",
            "AUTH_TOLERANCE_SECONDS": "0",
            "TOKEN_TTL_SECONDS": "-10",
            "LAST_ACT": "zero",
        })

    assert cfg.CHECKPOINTS == (100.0, 250.5)
    assert cfg.RATE_LIMIT_MAX == 60
    assert cfg.RATE_LIMIT_WINDOW == 60
    assert cfg.AUTH_TOLERANCE_SECONDS == 300
    assert cfg.TOKEN_TTL_SECONDS == 300
    assert cfg.LAST_ACT == 10
    assert "Invalid integer" in caplog.text
    assert "Out-of-range integer" in caplog.text
    assert "Ignoring invalid CHECKPOINTS entry" in caplog.text


def test_checkpoints_semicolon_typo_does_not_crash():
    cfg = api_config.load_config({"CHECKPOINTS": "1000;2500"})
    assert cfg.CHECKPOINTS == ()


def test_explicit_zero_or_negative_rate_limit_values_preserved():
    cfg = api_config.load_config({"RATE_LIMIT_MAX": "0", "RATE_LIMIT_WINDOW": "-1"})
    assert cfg.RATE_LIMIT_MAX == 0
    assert cfg.RATE_LIMIT_WINDOW == -1


def test_cors_and_oauth_urls_strip_trailing_slashes():
    cfg = api_config.load_config({
        "INTERVALS_OAUTH_BASE_URL": "https://mock.wiremockapi.cloud/",
        "CORS_ALLOWED_ORIGINS": "https://pre.example.com/, http://localhost:5173/ , *",
    })
    assert cfg.INTERVALS_OAUTH_BASE_URL == "https://mock.wiremockapi.cloud"
    assert cfg.CORS_ALLOWED_ORIGINS == ("https://pre.example.com", "http://localhost:5173", "*")


def test_app_config_is_immutable():
    cfg = api_config.load_config({})
    with pytest.raises(FrozenInstanceError):
        cfg.RATE_LIMIT_MAX = 999  # type: ignore[misc]

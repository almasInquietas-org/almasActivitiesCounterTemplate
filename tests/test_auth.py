import hmac
import hashlib
import time
import pytest
from api import auth, api_config


@pytest.fixture(autouse=True)
def reset_auth_state(monkeypatch):
    """Ensure clean auth state before each test."""
    auth.clear_tokens()
    monkeypatch.setattr(api_config, "API_KEY", "")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "")
    monkeypatch.setattr(api_config, "AUTH_TOLERANCE_SECONDS", 300)
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", 300)


def test_is_auth_disabled_when_keys_empty(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "")
    assert auth.is_auth_enabled() is False


def test_is_auth_enabled_when_keys_present(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")
    assert auth.is_auth_enabled() is True


def test_verify_signature_success(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")
    monkeypatch.setattr(api_config, "AUTH_TOLERANCE_SECONDS", 300)

    now_ts = str(time.time())
    nonce = "random-nonce-123"
    message = f"{now_ts}.{nonce}".encode("utf-8")
    valid_sig = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

    assert auth.verify_signature("test-key", now_ts, nonce, valid_sig) is True


def test_verify_signature_invalid_key(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")

    now_ts = str(time.time())
    nonce = "random-nonce-123"
    message = f"{now_ts}.{nonce}".encode("utf-8")
    sig = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

    assert auth.verify_signature("wrong-key", now_ts, nonce, sig) is False


def test_verify_signature_expired_timestamp(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")
    monkeypatch.setattr(api_config, "AUTH_TOLERANCE_SECONDS", 300)

    old_ts = str(time.time() - 301)
    nonce = "random-nonce-123"
    message = f"{old_ts}.{nonce}".encode("utf-8")
    sig = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

    assert auth.verify_signature("test-key", old_ts, nonce, sig) is False


def test_verify_signature_invalid_sig(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")

    now_ts = str(time.time())
    nonce = "random-nonce-123"
    assert auth.verify_signature("test-key", now_ts, nonce, "invalid-sig") is False


def test_generate_and_verify_token(monkeypatch):
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", 300)
    token, ttl = auth.generate_token()
    assert isinstance(token, str)
    assert ttl == 300
    assert auth.verify_token(token) is True
    assert auth.verify_token("unknown-token") is False


def test_verify_token_expired(monkeypatch):
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", 1)
    token, _ = auth.generate_token()
    # Fast forward or simulate expiration
    auth._active_tokens[token] = time.time() - 10
    assert auth.verify_token(token) is False

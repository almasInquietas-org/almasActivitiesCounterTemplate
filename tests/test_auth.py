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
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", 300)
    token, ttl = auth.generate_token()
    assert isinstance(token, str)
    assert len(token.split(".")) == 3
    assert ttl == 300
    assert auth.verify_token(token) is True
    assert auth.verify_token("unknown-token") is False


def test_verify_token_expired(monkeypatch):
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", -10)
    token, _ = auth.generate_token()
    assert auth.verify_token(token) is False


def test_stateless_token_verifies_across_containers_and_rejects_tampering(monkeypatch):
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "container-shared-secret")
    monkeypatch.setattr(api_config, "TOKEN_TTL_SECONDS", 300)

    assert not hasattr(auth, "_active_tokens")
    token, _ = auth.generate_token()

    # Simulate another Lambda container where local memory was reset
    auth.clear_tokens()
    assert auth.verify_token(token) is True

    exp_str, nonce, sig = token.split(".")
    assert auth.verify_token(f"{int(exp_str) + 100}.{nonce}.{sig}") is False
    assert auth.verify_token(f"{exp_str}.{nonce}.{'0' * len(sig)}") is False
    assert auth.verify_token(f"{exp_str}.{nonce}") is False

    # Domain separation: raw HMAC with API_SIGNING_SECRET must not verify as a Bearer token
    raw_sig = hmac.new(
        b"container-shared-secret",
        f"{exp_str}.{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert auth.verify_token(f"{exp_str}.{nonce}.{raw_sig}") is False

    # Wrong or missing secret fails closed
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "different-secret")
    assert auth.verify_token(token) is False
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "")
    assert auth.verify_token(token) is False


def test_verify_signature_rejects_nonce_replay_and_invalid_inputs(monkeypatch):
    monkeypatch.setattr(api_config, "API_KEY", "test-key")
    monkeypatch.setattr(api_config, "API_SIGNING_SECRET", "test-secret")
    monkeypatch.setattr(api_config, "AUTH_TOLERANCE_SECONDS", 300)

    now_ts = str(time.time())
    nonce = "unique-nonce-1"
    sig = hmac.new(b"test-secret", f"{now_ts}.{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()

    # Invalid signature must not poison the nonce cache
    assert auth.verify_signature("test-key", now_ts, nonce, "bad-sig") is False

    # First valid call succeeds; exact replay fails
    assert auth.verify_signature("test-key", now_ts, nonce, sig) is True
    assert auth.verify_signature("test-key", now_ts, nonce, sig) is False

    # Empty/whitespace nonce or NaN timestamp rejected
    assert auth.verify_signature("test-key", now_ts, "   ", sig) is False
    nan_sig = hmac.new(b"test-secret", f"nan.{nonce}2".encode("utf-8"), hashlib.sha256).hexdigest()
    assert auth.verify_signature("test-key", "nan", f"{nonce}2", nan_sig) is False

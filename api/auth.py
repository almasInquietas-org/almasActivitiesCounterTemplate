"""
auth.py - Frontend HMAC-SHA256 signature and Bearer token verification.
"""
import hmac
import hashlib
import time
import uuid
from api import api_config as config

_active_tokens: dict[str, float] = {}


def clear_tokens() -> None:
    """Helper to clear active tokens during tests."""
    global _active_tokens
    _active_tokens.clear()


def is_auth_enabled() -> bool:
    """
    Returns True if API_KEY and API_SIGNING_SECRET are both configured.
    If either is empty, auth is disabled (passthrough mode).
    """
    return bool(config.API_KEY and config.API_SIGNING_SECRET)


def verify_signature(api_key: str, timestamp: str, nonce: str, signature: str) -> bool:
    """
    Verifies that the API key matches and HMAC-SHA256(secret, f"{timestamp}.{nonce}")
    equals the provided signature within the allowed tolerance window.
    """
    if not is_auth_enabled():
        return True

    if not hmac.compare_digest(api_key, config.API_KEY):
        return False

    try:
        ts_float = float(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts_float) > config.AUTH_TOLERANCE_SECONDS:
        return False

    message = f"{timestamp}.{nonce}".encode("utf-8")
    expected_sig = hmac.new(
        config.API_SIGNING_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)


def generate_token() -> tuple[str, int]:
    """
    Generates a new Bearer token, stores it in memory with an expiration timestamp,
    and returns (token, ttl_seconds).
    """
    token = str(uuid.uuid4())
    ttl = config.TOKEN_TTL_SECONDS
    _active_tokens[token] = time.time() + ttl
    return token, ttl


def verify_token(token: str) -> bool:
    """
    Verifies that the Bearer token exists in _active_tokens and has not expired.
    Returns True if valid, else False.
    """
    expiry = _active_tokens.get(token)
    if not expiry:
        return False

    if time.time() > expiry:
        _active_tokens.pop(token, None)
        return False

    return True

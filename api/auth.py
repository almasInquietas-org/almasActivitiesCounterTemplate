"""
auth.py - Frontend HMAC-SHA256 signature and stateless Bearer token verification.
"""
import hashlib
import hmac
import math
import secrets
import time
from api import api_config as config

_BEARER_TOKEN_DOMAIN = b"almas-bearer-token-v1"
_MAX_TRACKED_NONCES = 10_000
_used_nonces: dict[str, float] = {}


def clear_tokens() -> None:
    """Helper to clear replay-protection nonce state during tests."""
    _used_nonces.clear()


def is_auth_enabled() -> bool:
    """
    Returns True if API_KEY and API_SIGNING_SECRET are both configured.
    If either is empty, auth is disabled (passthrough mode).
    """
    return bool(config.API_KEY and config.API_SIGNING_SECRET)


def _get_bearer_signing_key() -> bytes:
    """Derive a domain-separated HMAC key for stateless Bearer tokens."""
    secret = (config.API_SIGNING_SECRET or "").strip()
    if not secret:
        raise RuntimeError("API_SIGNING_SECRET must be configured to sign or verify Bearer tokens")
    return hmac.new(secret.encode("utf-8"), _BEARER_TOKEN_DOMAIN, hashlib.sha256).digest()


def verify_signature(api_key: str, timestamp: str, nonce: str, signature: str) -> bool:
    """
    Verifies that the API key matches, HMAC-SHA256(secret, f"{timestamp}.{nonce}")
    equals the provided signature within the allowed tolerance window, and the
    nonce has not already been used within the active tolerance window.
    """
    if not is_auth_enabled():
        return True

    if not api_key or not signature or not nonce or not str(nonce).strip():
        return False

    if not hmac.compare_digest(str(api_key), config.API_KEY):
        return False

    try:
        ts_float = float(timestamp)
    except (ValueError, TypeError):
        return False

    if not math.isfinite(ts_float):
        return False

    now = time.time()
    if abs(now - ts_float) > config.AUTH_TOLERANCE_SECONDS:
        return False

    message = f"{timestamp}.{nonce}".encode("utf-8")
    expected_sig = hmac.new(
        config.API_SIGNING_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, str(signature)):
        return False

    expired_nonces = [k for k, exp_ts in _used_nonces.items() if exp_ts <= now]
    for k in expired_nonces:
        del _used_nonces[k]

    if nonce in _used_nonces:
        return False

    if len(_used_nonces) >= _MAX_TRACKED_NONCES:
        _used_nonces.pop(next(iter(_used_nonces)), None)

    _used_nonces[nonce] = now + max(int(config.AUTH_TOLERANCE_SECONDS), 1)
    return True


def generate_token() -> tuple[str, int]:
    """
    Generates a stateless HMAC-SHA256 signed Bearer token (`<exp>.<nonce>.<sig>`)
    and returns (token, ttl_seconds).
    """
    ttl = int(config.TOKEN_TTL_SECONDS)
    exp = int(time.time()) + ttl
    nonce = secrets.token_hex(16)
    payload = f"{exp}.{nonce}"
    sig = hmac.new(
        _get_bearer_signing_key(),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{sig}", ttl


def verify_token(token: str) -> bool:
    """
    Verifies a stateless HMAC-SHA256 Bearer token's signature and expiration.
    Returns True if valid, else False.
    """
    if not isinstance(token, str) or not token:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False

    exp_str, nonce, sig = parts
    if not exp_str or not nonce or not sig:
        return False

    try:
        exp = int(exp_str)
    except ValueError:
        return False

    if time.time() > exp:
        return False

    try:
        signing_key = _get_bearer_signing_key()
    except RuntimeError:
        return False

    expected_sig = hmac.new(
        signing_key,
        f"{exp_str}.{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, sig)

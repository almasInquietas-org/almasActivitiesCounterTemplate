"""
rate_limiter.py - Sliding window in-memory rate limiter per IP.
"""
import time
from api import api_config as config

_MAX_TRACKED_IPS = 10_000
_request_history: dict[str, list[float]] = {}
_last_prune_ts: float = 0.0


def clear_history() -> None:
    """Helper to clear rate limit state during tests."""
    global _last_prune_ts
    _request_history.clear()
    _last_prune_ts = 0.0


def prune_expired(now: float | None = None) -> int:
    """Remove expired timestamps and stale IP keys with no remaining timestamps."""
    current_now = time.time() if now is None else now
    window_start = current_now - config.RATE_LIMIT_WINDOW
    removed = 0

    for ip, timestamps in list(_request_history.items()):
        active = [ts for ts in timestamps if ts > window_start]
        if active:
            _request_history[ip] = active
        else:
            _request_history.pop(ip, None)
            removed += 1

    return removed


def is_rate_limited(client_ip: str) -> bool:
    """
    Checks if client_ip has exceeded RATE_LIMIT_MAX within RATE_LIMIT_WINDOW seconds.
    Returns True if rate limited (blocked), False if allowed or rate limiting is disabled.
    """
    global _last_prune_ts
    if config.RATE_LIMIT_MAX <= 0 or config.RATE_LIMIT_WINDOW <= 0:
        return False

    now = time.time()
    window_start = now - config.RATE_LIMIT_WINDOW

    if (
        now - _last_prune_ts >= max(config.RATE_LIMIT_WINDOW, 1)
        or len(_request_history) >= _MAX_TRACKED_IPS
    ):
        prune_expired(now)
        _last_prune_ts = now

    # Filter timestamps within current window
    history = [ts for ts in _request_history.get(client_ip, []) if ts > window_start]

    if len(history) >= config.RATE_LIMIT_MAX:
        if history:
            _request_history[client_ip] = history
        else:
            _request_history.pop(client_ip, None)
        return True

    if client_ip not in _request_history and len(_request_history) >= _MAX_TRACKED_IPS:
        _request_history.pop(next(iter(_request_history)), None)

    history.append(now)
    _request_history[client_ip] = history
    return False

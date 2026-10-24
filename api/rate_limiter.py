"""
rate_limiter.py - Sliding window in-memory rate limiter per IP.
"""
import time
from api import api_config as config

_request_history: dict[str, list[float]] = {}


def clear_history() -> None:
    """Helper to clear rate limit state during tests."""
    global _request_history
    _request_history.clear()


def is_rate_limited(client_ip: str) -> bool:
    """
    Checks if client_ip has exceeded RATE_LIMIT_MAX within RATE_LIMIT_WINDOW seconds.
    Returns True if rate limited (blocked), False if allowed.
    """
    now = time.time()
    window_start = now - config.RATE_LIMIT_WINDOW

    # Filter timestamps within current window
    history = _request_history.get(client_ip, [])
    history = [ts for ts in history if ts > window_start]

    if len(history) >= config.RATE_LIMIT_MAX:
        _request_history[client_ip] = history
        return True

    history.append(now)
    _request_history[client_ip] = history
    return False

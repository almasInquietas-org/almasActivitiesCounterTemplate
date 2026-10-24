import pytest
from api import rate_limiter, api_config


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.clear_history()


def test_rate_limiter_allows_under_limit(monkeypatch):
    monkeypatch.setattr(api_config, "RATE_LIMIT_MAX", 3)
    monkeypatch.setattr(api_config, "RATE_LIMIT_WINDOW", 60)

    ip = "192.168.1.1"
    assert rate_limiter.is_rate_limited(ip) is False
    assert rate_limiter.is_rate_limited(ip) is False
    assert rate_limiter.is_rate_limited(ip) is False
    assert rate_limiter.is_rate_limited(ip) is True


def test_rate_limiter_differentiates_ips(monkeypatch):
    monkeypatch.setattr(api_config, "RATE_LIMIT_MAX", 2)
    monkeypatch.setattr(api_config, "RATE_LIMIT_WINDOW", 60)

    ip1 = "10.0.0.1"
    ip2 = "10.0.0.2"

    assert rate_limiter.is_rate_limited(ip1) is False
    assert rate_limiter.is_rate_limited(ip1) is False
    assert rate_limiter.is_rate_limited(ip1) is True

    # ip2 is unaffected
    assert rate_limiter.is_rate_limited(ip2) is False


def test_rate_limiter_window_expiry(monkeypatch):
    monkeypatch.setattr(api_config, "RATE_LIMIT_MAX", 1)
    monkeypatch.setattr(api_config, "RATE_LIMIT_WINDOW", 5)

    ip = "127.0.0.1"
    assert rate_limiter.is_rate_limited(ip) is False
    assert rate_limiter.is_rate_limited(ip) is True

    # Artificially expire the timestamp in history
    rate_limiter._request_history[ip] = [100.0]
    assert rate_limiter.is_rate_limited(ip) is False

import os
import pytest
from api import api_config


def test_api_config_defaults():
    assert api_config.ATHLETES_TABLE_NAME == "ATHLETES_DEV"
    assert api_config.ACTIVITIES_TABLE_NAME == "ACTIVITIES_DEV"
    assert api_config.INTERVALS_OAUTH_BASE_URL == "https://intervals.icu"
    assert api_config.AUTH_TOLERANCE_SECONDS == 300
    assert api_config.TOKEN_TTL_SECONDS == 300
    assert api_config.RATE_LIMIT_MAX == 30
    assert api_config.RATE_LIMIT_WINDOW == 60
    assert api_config.CORS_ALLOWED_ORIGINS == ["*"]


def test_api_config_dashboard_defaults():
    assert api_config.GOAL_KM == 500.0
    assert api_config.LAST_ACT == 10
    assert api_config.TITLE == "Almas Inquietas Activities"
    assert isinstance(api_config.CHECKPOINTS, list)

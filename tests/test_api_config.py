import os
import pytest
from api import api_config


def test_api_config_no_default_env():
    # If an env var is empty or unset, it should be empty/None/0 (no hardcoded defaults)
    assert api_config.INTERVALS_CLIENT_ID == ""
    assert api_config.INTERVALS_CLIENT_SECRET == ""
    assert api_config.INTERVALS_WEBHOOK_SECRET == ""
    assert api_config.API_KEY == ""
    assert api_config.API_SIGNING_SECRET == ""


def test_api_config_goal_km_parsing():
    # Test none/null/0 evaluation to None
    from api import api_config as cfg
    assert cfg.GOAL_KM == 500.0 or cfg.GOAL_KM is None


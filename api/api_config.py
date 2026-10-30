"""
api_config.py - Environment variable configuration without default setups.
All configuration is loaded directly from environment variables.
"""
import os

# AWS / DynamoDB
AWS_REGION: str = os.environ.get("AWS_REGION", "")
ATHLETES_TABLE_NAME: str = os.environ.get("ATHLETES_TABLE_NAME", "")
ACTIVITIES_TABLE_NAME: str = os.environ.get("ACTIVITIES_TABLE_NAME", "")

# Intervals.icu OAuth & Webhooks
INTERVALS_OAUTH_BASE_URL: str = os.environ.get("INTERVALS_OAUTH_BASE_URL", "")
INTERVALS_CLIENT_ID: str = os.environ.get("INTERVALS_CLIENT_ID", "")
INTERVALS_CLIENT_SECRET: str = os.environ.get("INTERVALS_CLIENT_SECRET", "")
INTERVALS_WEBHOOK_SECRET: str = os.environ.get("INTERVALS_WEBHOOK_SECRET", "")

# Dashboard & Business Logic
_goal_env: str = os.environ.get("GOAL_KM", "").strip()
GOAL_KM: float | None = (
    float(_goal_env)
    if _goal_env and _goal_env.lower() not in ("none", "null", "0")
    else None
)
_last_act_env: str = os.environ.get("LAST_ACT", "").strip()
LAST_ACT: int = int(_last_act_env) if _last_act_env else 0
TITLE: str = os.environ.get("TITLE", "")
_checkpoints_env: str = os.environ.get("CHECKPOINTS", "")
CHECKPOINTS: list[float] = [
    float(cp.strip())
    for cp in _checkpoints_env.split(",")
    if cp.strip()
]
ACT_TYPE_FILTER: str = os.environ.get("ACT_TYPE_FILTER", "")
ACT_TITLE_FILTER: str = os.environ.get("ACT_TITLE_FILTER", "")
START_DATE: str = os.environ.get("START_DATE", "")
CLUB_FILTER: str = os.environ.get("CLUB_FILTER", "")

# Security & Auth
API_KEY: str = os.environ.get("API_KEY", "")
API_SIGNING_SECRET: str = os.environ.get("API_SIGNING_SECRET", "")
_tolerance_env: str = os.environ.get("AUTH_TOLERANCE_SECONDS", "").strip()
AUTH_TOLERANCE_SECONDS: int = int(_tolerance_env) if _tolerance_env else 0
_ttl_env: str = os.environ.get("TOKEN_TTL_SECONDS", "").strip()
TOKEN_TTL_SECONDS: int = int(_ttl_env) if _ttl_env else 0

# Rate Limiter
_limit_max_env: str = os.environ.get("RATE_LIMIT_MAX", "").strip()
RATE_LIMIT_MAX: int = int(_limit_max_env) if _limit_max_env else 0
_limit_window_env: str = os.environ.get("RATE_LIMIT_WINDOW", "").strip()
RATE_LIMIT_WINDOW: int = int(_limit_window_env) if _limit_window_env else 0

# CORS
_cors_env: str = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS: list[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]


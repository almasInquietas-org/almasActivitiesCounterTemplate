"""
api_config.py - Environment variable configuration with defaults for DEV, PRE, and PROD.
"""
import os

# AWS / DynamoDB
AWS_REGION: str = os.environ.get("AWS_REGION", "eu-west-1")
ATHLETES_TABLE_NAME: str = os.environ.get("ATHLETES_TABLE_NAME", "ATHLETES_DEV")
ACTIVITIES_TABLE_NAME: str = os.environ.get("ACTIVITIES_TABLE_NAME", "ACTIVITIES_DEV")

# Intervals.icu OAuth & Webhooks
INTERVALS_OAUTH_BASE_URL: str = os.environ.get("INTERVALS_OAUTH_BASE_URL", "https://intervals.icu")
INTERVALS_CLIENT_ID: str = os.environ.get("INTERVALS_CLIENT_ID", "")
INTERVALS_CLIENT_SECRET: str = os.environ.get("INTERVALS_CLIENT_SECRET", "")
INTERVALS_WEBHOOK_SECRET: str = os.environ.get("INTERVALS_WEBHOOK_SECRET", "")

# Dashboard & Business Logic
GOAL_KM: float | None = float(os.environ["GOAL_KM"]) if os.environ.get("GOAL_KM") else None
LAST_ACT: int = int(os.environ.get("LAST_ACT"))
TITLE: str = os.environ.get("TITLE")
CHECKPOINTS: list[float] = [
    float(cp.strip())
    for cp in os.environ.get("CHECKPOINTS").split(",")
    if cp.strip()
]
ACT_TYPE_FILTER: str = os.environ.get("ACT_TYPE_FILTER")
ACT_TITLE_FILTER: str = os.environ.get("ACT_TITLE_FILTER")
START_DATE: str = os.environ.get("START_DATE")
CLUB_FILTER: str = os.environ.get("CLUB_FILTER")

# Security & Auth
API_KEY: str = os.environ.get("API_KEY")
API_SIGNING_SECRET: str = os.environ.get("API_SIGNING_SECRET")
AUTH_TOLERANCE_SECONDS: int = int(os.environ.get("AUTH_TOLERANCE_SECONDS", "300"))
TOKEN_TTL_SECONDS: int = int(os.environ.get("TOKEN_TTL_SECONDS", "300"))

# Rate Limiter
RATE_LIMIT_MAX: int = int(os.environ.get("RATE_LIMIT_MAX", "30"))
RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

# CORS
_cors_env: str = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
CORS_ALLOWED_ORIGINS: list[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

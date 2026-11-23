"""
api_config.py - Typed, validated environment variable configuration with safe defaults.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import logging
import math
import os

logger = logging.getLogger(__name__)

DEFAULT_INTERVALS_OAUTH_BASE_URL = "https://intervals.icu"
DEFAULT_LAST_ACT = 10
DEFAULT_TITLE = "Almas Inquietas Activities"
DEFAULT_AUTH_TOLERANCE_SECONDS = 300
DEFAULT_TOKEN_TTL_SECONDS = 300
DEFAULT_RATE_LIMIT_MAX = 60
DEFAULT_RATE_LIMIT_WINDOW = 60


def _parse_str(environ: Mapping[str, str], name: str, default: str = "") -> str:
    value = str(environ.get(name, "") or "").strip()
    return value if value else default


def _parse_int(
    environ: Mapping[str, str],
    name: str,
    default: int,
    *,
    min_value: int | None = None,
) -> int:
    raw = str(environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid integer for %s=%r; falling back to default %d",
            name,
            raw,
            default,
        )
        return default

    if min_value is not None and value < min_value:
        logger.warning(
            "Out-of-range integer for %s=%d (minimum %d); falling back to default %d",
            name,
            value,
            min_value,
            default,
        )
        return default

    return value


def _parse_goal_km(raw_value: str) -> float | None:
    raw = (raw_value or "").strip()
    if not raw or raw.lower() in ("none", "null"):
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid GOAL_KM=%r; treating goal as disabled (None)", raw)
        return None

    if not math.isfinite(value) or value <= 0:
        if not math.isfinite(value) or value < 0:
            logger.warning("Non-positive/non-finite GOAL_KM=%r; treating goal as disabled (None)", raw)
        return None

    return value


def _parse_checkpoints(raw_value: str) -> tuple[float, ...]:
    checkpoints: list[float] = []
    for token in (raw_value or "").split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        try:
            value = float(cleaned)
        except ValueError:
            logger.warning("Ignoring invalid CHECKPOINTS entry %r", cleaned)
            continue
        if not math.isfinite(value) or value <= 0:
            logger.warning("Ignoring non-positive/non-finite CHECKPOINTS entry %r", cleaned)
            continue
        checkpoints.append(value)
    return tuple(checkpoints)


def _parse_cors_origins(raw_value: str) -> tuple[str, ...]:
    origins: list[str] = []
    for token in (raw_value or "").split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        origins.append("*" if cleaned == "*" else cleaned.rstrip("/"))
    return tuple(origins)


@dataclass(frozen=True)
class AppConfig:
    """Immutable, validated application configuration loaded from environment variables."""

    AWS_REGION: str
    ATHLETES_TABLE_NAME: str
    ACTIVITIES_TABLE_NAME: str
    INTERVALS_OAUTH_BASE_URL: str
    INTERVALS_CLIENT_ID: str
    INTERVALS_CLIENT_SECRET: str
    INTERVALS_WEBHOOK_SECRET: str
    GOAL_KM: float | None
    LAST_ACT: int
    TITLE: str
    CHECKPOINTS: tuple[float, ...]
    ACT_TYPE_FILTER: str
    ACT_TITLE_FILTER: str
    START_DATE: str
    CLUB_FILTER: str
    API_KEY: str
    API_SIGNING_SECRET: str
    AUTH_TOLERANCE_SECONDS: int
    TOKEN_TTL_SECONDS: int
    RATE_LIMIT_MAX: int
    RATE_LIMIT_WINDOW: int
    CORS_ALLOWED_ORIGINS: tuple[str, ...]


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    """Parse and validate environment variables into an immutable AppConfig."""
    env = os.environ if environ is None else environ
    oauth_url = _parse_str(env, "INTERVALS_OAUTH_BASE_URL", DEFAULT_INTERVALS_OAUTH_BASE_URL).rstrip("/")
    return AppConfig(
        AWS_REGION=_parse_str(env, "AWS_REGION"),
        ATHLETES_TABLE_NAME=_parse_str(env, "ATHLETES_TABLE_NAME"),
        ACTIVITIES_TABLE_NAME=_parse_str(env, "ACTIVITIES_TABLE_NAME"),
        INTERVALS_OAUTH_BASE_URL=oauth_url or DEFAULT_INTERVALS_OAUTH_BASE_URL,
        INTERVALS_CLIENT_ID=_parse_str(env, "INTERVALS_CLIENT_ID"),
        INTERVALS_CLIENT_SECRET=_parse_str(env, "INTERVALS_CLIENT_SECRET"),
        INTERVALS_WEBHOOK_SECRET=_parse_str(env, "INTERVALS_WEBHOOK_SECRET"),
        GOAL_KM=_parse_goal_km(str(env.get("GOAL_KM", "") or "")),
        LAST_ACT=_parse_int(env, "LAST_ACT", DEFAULT_LAST_ACT, min_value=1),
        TITLE=_parse_str(env, "TITLE", DEFAULT_TITLE),
        CHECKPOINTS=_parse_checkpoints(str(env.get("CHECKPOINTS", "") or "")),
        ACT_TYPE_FILTER=_parse_str(env, "ACT_TYPE_FILTER"),
        ACT_TITLE_FILTER=_parse_str(env, "ACT_TITLE_FILTER"),
        START_DATE=_parse_str(env, "START_DATE"),
        CLUB_FILTER=_parse_str(env, "CLUB_FILTER"),
        API_KEY=_parse_str(env, "API_KEY"),
        API_SIGNING_SECRET=_parse_str(env, "API_SIGNING_SECRET"),
        AUTH_TOLERANCE_SECONDS=_parse_int(
            env,
            "AUTH_TOLERANCE_SECONDS",
            DEFAULT_AUTH_TOLERANCE_SECONDS,
            min_value=1,
        ),
        TOKEN_TTL_SECONDS=_parse_int(
            env,
            "TOKEN_TTL_SECONDS",
            DEFAULT_TOKEN_TTL_SECONDS,
            min_value=1,
        ),
        RATE_LIMIT_MAX=_parse_int(env, "RATE_LIMIT_MAX", DEFAULT_RATE_LIMIT_MAX),
        RATE_LIMIT_WINDOW=_parse_int(env, "RATE_LIMIT_WINDOW", DEFAULT_RATE_LIMIT_WINDOW),
        CORS_ALLOWED_ORIGINS=_parse_cors_origins(str(env.get("CORS_ALLOWED_ORIGINS", "") or "")),
    )


CONFIG: AppConfig
AWS_REGION: str
ATHLETES_TABLE_NAME: str
ACTIVITIES_TABLE_NAME: str
INTERVALS_OAUTH_BASE_URL: str
INTERVALS_CLIENT_ID: str
INTERVALS_CLIENT_SECRET: str
INTERVALS_WEBHOOK_SECRET: str
GOAL_KM: float | None
LAST_ACT: int
TITLE: str
CHECKPOINTS: list[float]
ACT_TYPE_FILTER: str
ACT_TITLE_FILTER: str
START_DATE: str
CLUB_FILTER: str
API_KEY: str
API_SIGNING_SECRET: str
AUTH_TOLERANCE_SECONDS: int
TOKEN_TTL_SECONDS: int
RATE_LIMIT_MAX: int
RATE_LIMIT_WINDOW: int
CORS_ALLOWED_ORIGINS: list[str]


def apply_config(cfg: AppConfig) -> None:
    """Bind an AppConfig instance to module-level attributes for backward compatibility."""
    global CONFIG
    global AWS_REGION, ATHLETES_TABLE_NAME, ACTIVITIES_TABLE_NAME
    global INTERVALS_OAUTH_BASE_URL, INTERVALS_CLIENT_ID, INTERVALS_CLIENT_SECRET, INTERVALS_WEBHOOK_SECRET
    global GOAL_KM, LAST_ACT, TITLE, CHECKPOINTS
    global ACT_TYPE_FILTER, ACT_TITLE_FILTER, START_DATE, CLUB_FILTER
    global API_KEY, API_SIGNING_SECRET, AUTH_TOLERANCE_SECONDS, TOKEN_TTL_SECONDS
    global RATE_LIMIT_MAX, RATE_LIMIT_WINDOW, CORS_ALLOWED_ORIGINS

    CONFIG = cfg
    AWS_REGION = cfg.AWS_REGION
    ATHLETES_TABLE_NAME = cfg.ATHLETES_TABLE_NAME
    ACTIVITIES_TABLE_NAME = cfg.ACTIVITIES_TABLE_NAME
    INTERVALS_OAUTH_BASE_URL = cfg.INTERVALS_OAUTH_BASE_URL
    INTERVALS_CLIENT_ID = cfg.INTERVALS_CLIENT_ID
    INTERVALS_CLIENT_SECRET = cfg.INTERVALS_CLIENT_SECRET
    INTERVALS_WEBHOOK_SECRET = cfg.INTERVALS_WEBHOOK_SECRET
    GOAL_KM = cfg.GOAL_KM
    LAST_ACT = cfg.LAST_ACT
    TITLE = cfg.TITLE
    CHECKPOINTS = list(cfg.CHECKPOINTS)
    ACT_TYPE_FILTER = cfg.ACT_TYPE_FILTER
    ACT_TITLE_FILTER = cfg.ACT_TITLE_FILTER
    START_DATE = cfg.START_DATE
    CLUB_FILTER = cfg.CLUB_FILTER
    API_KEY = cfg.API_KEY
    API_SIGNING_SECRET = cfg.API_SIGNING_SECRET
    AUTH_TOLERANCE_SECONDS = cfg.AUTH_TOLERANCE_SECONDS
    TOKEN_TTL_SECONDS = cfg.TOKEN_TTL_SECONDS
    RATE_LIMIT_MAX = cfg.RATE_LIMIT_MAX
    RATE_LIMIT_WINDOW = cfg.RATE_LIMIT_WINDOW
    CORS_ALLOWED_ORIGINS = list(cfg.CORS_ALLOWED_ORIGINS)


apply_config(load_config())


# almasActivitiesCounterTemplate — Workspace Rules

## 1. Project Overview
Multi-club activity dashboard powered by **Intervals.icu OAuth 2.0 + Webhooks**, **AWS Lambda (Python 3.12)**, **AWS DynamoDB (`eu-west-1`)**, and **React 19 + Vite 7**.
Full architecture and API contracts are defined in `MIGRATION_PLAN.md`, and the Agile implementation backlog is in `MIGRATION_STORIES.md`.

## 2. Non-Negotiable Guardrails
1. **Flat Imports Inside `api/` (Critical for AWS Lambda):**
   - In production, the *contents* of `api/` are zipped at the root of the Lambda package.
   - Inside `api/*.py`, **ALWAYS use flat imports**:
     - `import api_config as config`
     - `import auth`, `import rate_limiter`, `import db`, `import services`, `import utils`, `import intervals_oauth`
   - **NEVER** use `from api import ...` or relative `from . import ...` inside `api/*.py`.
   - In `tests/conftest.py`, always insert `str(Path(__file__).resolve().parent.parent / "api")` into `sys.path` at the very top of the file before importing any `api` modules.
2. **Lazy Boto3 Table Access in `api/db.py` (Critical for `moto` tests):**
   - Do not cache `boto3.resource('dynamodb').Table(...)` at module import time. Instead, use small helper functions (`_get_athletes_table()` and `_get_activities_table()`) that read `config.AWS_REGION`, `config.ATHLETES_TABLE_NAME`, and `config.ACTIVITIES_TABLE_NAME` on call. This guarantees `moto` fixtures and `monkeypatch` work without import-order bugs.
3. **Zero External Pip Dependencies in `api/`:**
   - The AWS Lambda runtime (`python3.12`) already provides `boto3`.
   - Use Python standard library (`urllib.request`, `urllib.parse`, `hmac`, `hashlib`, `json`, `decimal`, `html`) for all HTTP, OAuth, and crypto logic inside `api/`. Do not import `requests` inside `api/` so Lambda zip deployments require no `pip install` step.
4. **3-Environment Isolation (`DEV/QA`, `PRE`, `PROD`):**
   - Never hardcode table names or the Intervals.icu OAuth base URL. Always read `config.ATHLETES_TABLE_NAME`, `config.ACTIVITIES_TABLE_NAME`, and `config.INTERVALS_OAUTH_BASE_URL` from `api/api_config.py`.
   - All AWS resources live in `eu-west-1` separated by suffixes (`_DEV`, `_PRE`, `_PROD`).
5. **Branch Protection & Git Discipline:**
   - `master` (`PROD`) and `pre` (`PRE`) are protected branches. Never push directly to `master`.
   - Implement each Agile story on an isolated branch (`feature/story-<N>-<short-name>`).
6. **Verification Before Completion:**
   - Never mark a story or task complete without running `pytest tests/ -v` in the terminal and confirming 100% of tests pass.
   - Keep `frontend/` backward-compatible with the `GET /` and `POST /auth/token` contracts defined in Section 6 of `MIGRATION_PLAN.md`.

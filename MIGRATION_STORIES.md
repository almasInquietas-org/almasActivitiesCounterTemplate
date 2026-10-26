# Agile Backlog: New Repository & 3-Environment Setup (`DEV/QA`, `PRE`, `PROD`)

This backlog breaks down the new repository implementation into **8 small, independent, testable stories** covering the core application, the **WireMock** mocking infrastructure (`DEV/QA` + `PRE`), the demo data seeder/simulator, and the 3-environment CI/CD pipeline (`DEV/QA` → `PRE` → `PROD`).

---

## 🗺️ Story Dependency Map

```
┌──────────────────┐
│     Story 1      │  Repo Bootstrap, Multi-Env Config & Moto Harness
│  Repo & Config   │  (Adds INTERVALS_OAUTH_BASE_URL for WireMock switching)
└────────┬─────────┘
         │
         ├─────────────────────────────┐
         ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│     Story 2      │          │     Story 4      │
│  Athletes DB     │          │  OAuth Client    │  (Uses INTERVALS_OAUTH_BASE_URL
│  Layer (db.py)   │          │ (intervals_oauth)│   so WireMock & Prod work identically)
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│     Story 3      │          │     Story 5      │
│  Activities DB   │          │GET /oauth/callback│
│  & Aggregation   │          │   Route Handler  │
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
               ┌──────────────────┐
               │     Story 6      │
               │  POST /webhook   │
               │   Route Handler  │
               └────────┬─────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│     Story 7      │          │     Story 8      │
│ WireMock Stubs & │          │ 3-Env CI/CD      │
│ PRE Demo Scripts │          │ (QA, PRE, PROD)  │
└──────────────────┘          └──────────────────┘
```

---

## 🔒 Exact Cross-Story Function Signatures & Return Contracts

To allow any model (including fast/low-cost models) to implement each story in separate sessions without interface mismatches, **all stories MUST adhere to these exact function names, arguments, and return structures**:

| Story | Module | Exact Function Signature | Exact Return Type & Structure |
|---|---|---|---|
| **Story 1** | `api/auth.py` | `is_auth_enabled() -> bool` | `bool(config.API_KEY and config.API_SIGNING_SECRET)` |
| **Story 1** | `api/auth.py` | `verify_signature(api_key: str, timestamp: str, nonce: str, signature: str) -> bool` | `True` if valid HMAC-SHA256 within `AUTH_TOLERANCE_SECONDS`, else `False` |
| **Story 1** | `api/auth.py` | `generate_token() -> tuple[str, int]` | `(token_uuid_str, config.TOKEN_TTL_SECONDS)` |
| **Story 1** | `api/auth.py` | `verify_token(token: str) -> bool` | `True` if token is in `_active_tokens` and not expired, else `False` |
| **Story 1** | `api/rate_limiter.py` | `is_rate_limited(client_ip: str) -> bool` | `True` if requests in window `>= config.RATE_LIMIT_MAX`, else `False` |
| **Story 1** | `api/utils.py` | `class DecimalEncoder(json.JSONEncoder)` | Converts `Decimal` to `int` (if `obj % 1 == 0`) or `float` |
| **Story 2** | `api/db.py` | `save_athlete(athlete_id: str, athlete_name: str, access_token: str, club_id: str) -> dict` | Returns stored item: `{"athlete_id": str, "athlete_name": str, "access_token": str, "clubs": list[str], "updated_at": str}` |
| **Story 2** | `api/db.py` | `get_athlete(athlete_id: str) -> dict \| None` | Returns item dict from `ATHLETES_TABLE_NAME` or `None` if not found |
| **Story 3** | `api/db.py` | `save_activity(activity: dict, athlete_id: str, athlete_name: str, clubs: list[str]) -> bool` | `True` if new item inserted into `ACTIVITIES_TABLE_NAME`; `False` if duplicate (`ConditionalCheckFailedException`) |
| **Story 3** | `api/db.py` | `get_all_activities() -> list[dict]` | Full paginated scan of `ACTIVITIES_TABLE_NAME` |
| **Story 3** | `api/services.py` | `build_dashboard_data(club_filter: str \| None = None) -> dict` | `{"total_km": float, "total_activities": int, "top_athletes": list[dict], "last_activities": list[dict], "config": {"goal_km": float \| None, "title": str, "checkpoints": list[float]}}` |
| **Story 4** | `api/intervals_oauth.py` | `exchange_code_for_token(code: str) -> dict` | `{"access_token": str, "athlete_id": str, "athlete_name": str}` (raises `OAuthError` on failure) |
| **Story 4** | `api/intervals_oauth.py` | `render_callback_html(success: bool, athlete_name: str = "", club_id: str = "", error_msg: str = "") -> str` | Complete HTML string with escaped variables |
| **Story 5 & 6** | `api/backend_source.py` | `process_activities(event: dict, context: object) -> dict` | `{"statusCode": int, "headers": dict, "body": str}` |

---

## 📦 Agile Technical Stories

### Story 1: Repository Bootstrap, Core Security Helpers & Test Harness
- **As a** developer,
- **I want** to initialize the new repository (starting with only `frontend/`, `MIGRATION_PLAN.md`, and `MIGRATION_STORIES.md`) and implement `api_config.py`, `auth.py`, `rate_limiter.py`, `utils.py`, and `pytest` + `moto` fixtures from scratch,
- **So that** the new repository is 100% self-contained without needing the old POC backend code.

#### Acceptance Criteria
1. New repository structure contains `api/`, `frontend/`, `mocks/`, `scripts/`, `tests/`, and `.github/workflows/`.
2. `api/api_config.py` defines:
   - `ATHLETES_TABLE_NAME` (default `'ATHLETES_DEV'`)
   - `ACTIVITIES_TABLE_NAME` (default `'ACTIVITIES_DEV'`)
   - `INTERVALS_OAUTH_BASE_URL` (default `'https://intervals.icu'`, overridable to `http://localhost:8089` in DEV or WireMock Cloud URL in PRE)
   - `INTERVALS_CLIENT_ID`, `INTERVALS_CLIENT_SECRET`, `INTERVALS_WEBHOOK_SECRET`
   - Dashboard & auth config (`GOAL_KM`, `LAST_ACT`, `TITLE`, `CHECKPOINTS`, `ACT_TYPE_FILTER`, `ACT_TITLE_FILTER`, `START_DATE`, `CLUB_FILTER`, `API_KEY`, `API_SIGNING_SECRET`, `AUTH_TOLERANCE_SECONDS`, `TOKEN_TTL_SECONDS`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`, `CORS_ALLOWED_ORIGINS`).
3. `api/auth.py`, `api/rate_limiter.py`, and `api/utils.py` (`DecimalEncoder`) are implemented per Section 6 of `MIGRATION_PLAN.md`.
4. `tests/conftest.py` sets up mocked `ATHLETES_DEV` (PK: `athlete_id`) and `ACTIVITIES_DEV` (PK: `activity_id`) tables in `moto`.
5. Unit tests in `test_auth.py`, `test_rate_limiter.py`, and `test_api_config.py` pass 100%.

#### Technical Tasks
- [x] Create new repo containing `frontend/`, `MIGRATION_PLAN.md`, and `MIGRATION_STORIES.md`.
- [x] Implement `api/api_config.py`, `api/auth.py`, `api/rate_limiter.py`, and `api/utils.py`.
- [x] Configure `tests/conftest.py` with the 2 DynamoDB table fixtures.
- [x] Write and run `pytest` on `test_auth.py`, `test_rate_limiter.py`, and `test_api_config.py`.

---

### Story 2: Athlete & Club Data Access Layer (`ATHLETES_<ENV>`)
- **As a** backend service,
- **I want** database functions in `api/db.py` to register athletes by their unique `athlete_id` and manage their club memberships,
- **So that** we eliminate athlete name collisions and know which clubs each athlete belongs to.

#### Acceptance Criteria
1. `save_athlete(athlete_id, athlete_name, access_token, club_id)`:
   - Creates or updates the athlete item in `ATHLETES_TABLE_NAME`.
   - Stores `clubs` as a list of unique club IDs (e.g., if an athlete registers for `club_a` and later clicks `club_b`'s link, their `clubs` becomes `["club_a", "club_b"]`).
2. `get_athlete(athlete_id)`:
   - Retrieves the athlete dict (`athlete_id`, `athlete_name`, `clubs`, `access_token`) in $O(1)$ via `get_item`.
   - Returns `None` if the athlete is not registered.
3. Unit tests in `tests/test_db.py` verify new athlete creation, multi-club registration without duplicates, token update, and unknown athlete lookup.

#### Technical Tasks
- [x] Implement `save_athlete()` and `get_athlete()` in `api/db.py`.
- [x] Write unit tests in `tests/test_db.py` using `moto`.

---

### Story 3: Activity Persistence & Dashboard Aggregation (`ACTIVITIES_<ENV>`)
- **As a** backend service,
- **I want** to store Intervals.icu activities in `ACTIVITIES_TABLE_NAME` and aggregate them for the dashboard,
- **So that** `GET /` returns accurate total km, recent activities, and top 10 athletes without needing a separate counter table.

#### Acceptance Criteria
1. `save_activity(activity, athlete_id, athlete_name, clubs)` in `api/db.py`:
   - Uses `str(activity['id'])` as `activity_id` (PK).
   - Stores `athlete_id`, `athlete` (`athlete_name`), `clubs`, `title`, `type`, `sport_type`, `distance_km` (`Decimal`), `moving_time_seconds`, `total_elevation_gain`, and `start_date` (`start_date_local`).
   - Uses `ConditionExpression='attribute_not_exists(activity_id)'` so duplicate webhooks are safely ignored and return `False`.
   - Returns `True` when a new activity is saved.
2. `build_dashboard_data(club_filter=None)` in `api/services.py`:
   - Filters activities by `club_filter` (if provided), sport type, title, and start date.
   - Groups leaderboard stats by `athlete_id` (preventing name collisions between two people with the same name) while outputting `athlete_name`, `currentKm`, and `lastIncrement`.
3. Unit tests in `tests/test_db.py` and `tests/test_services.py` verify idempotency, club filtering, and collision-free athlete ranking.

#### Technical Tasks
- [x] Implement `save_activity()` and `get_all_activities()` in `api/db.py`.
- [x] Update `build_dashboard_data()` in `api/services.py` to support `athlete_id` grouping and optional `club_filter`.
- [x] Write unit tests in `tests/test_db.py` and `tests/test_services.py`.

---

### Story 4: Configurable OAuth Client & Confirmation Page (`api/intervals_oauth.py`)
- **As a** backend service,
- **I want** a standalone OAuth helper module that targets `config.INTERVALS_OAUTH_BASE_URL` using `urllib.request`,
- **So that** token exchange works seamlessly against local WireMock (`DEV`), WireMock Cloud (`PRE`), and real Intervals.icu (`PROD`).

#### Acceptance Criteria
1. `exchange_code_for_token(code: str) -> dict`:
   - Sends `POST {config.INTERVALS_OAUTH_BASE_URL}/api/oauth/token` (`application/x-www-form-urlencoded`) with `client_id`, `client_secret`, and `code`.
   - Parses the upstream response (`{"access_token": ..., "athlete": {"id": ..., "name": ...}}`) and returns a normalized dict: `{"access_token": str, "athlete_id": str, "athlete_name": str}`.
   - Raises a descriptive `OAuthError` if the server returns an HTTP error or invalid payload.
2. `render_callback_html(success: bool, athlete_name: str = "", club_id: str = "", error_msg: str = "") -> str`:
   - Returns a responsive, styled HTML page matching the dashboard teal aesthetic confirming registration (or explaining the error).
3. Unit tests in `tests/test_intervals_oauth.py` verify custom base URL routing, 200 OK parsing, 400 Bad Request handling, and HTML rendering.

#### Technical Tasks
- [x] Create `api/intervals_oauth.py`.
- [x] Write unit tests in `tests/test_intervals_oauth.py`.

---

### Story 5: Club Registration Callback Route (`GET /oauth/callback`)
- **As a** club member (or demo presenter in `PRE`),
- **I want** to click a club registration link and get registered to that club with a styled confirmation screen,
- **So that** onboarding works in both live production and client demos.

#### Acceptance Criteria
1. `_parse_event()` in `api/backend_source.py` extracts `queryStringParameters` and `body` from both Lambda Function URL v1.0 and v2.0 payloads.
2. `GET /oauth/callback`:
   - Reads `code` and `state` (`club_id`, defaults to `'default'`).
   - Returns `400` HTML error page if `code` is missing or `error=access_denied` is present.
   - Calls `intervals_oauth.exchange_code_for_token(code)` and `db.save_athlete(...)`.
   - Returns `200 OK` with `Content-Type: text/html` confirmation page.
3. Unit tests in `tests/test_backend_source.py` test valid callback, denied callback, missing code, and failed token exchange.

#### Technical Tasks
- [x] Enhance `_parse_event()` and add `_make_html_response()` in `api/backend_source.py`.
- [x] Implement `_handle_oauth_callback()` in `api/backend_source.py` and wire route in local Flask runner.
- [x] Add unit tests in `tests/test_backend_source.py`.

---

### Story 6: Real-Time Webhook Receiver Route (`POST /webhook`)
- **As a** system,
- **I want** to receive `ACTIVITY_UPLOADED` webhooks and persist new workouts,
- **So that** the dashboard updates automatically in real time whenever a workout is uploaded (or simulated in `PRE`).

#### Acceptance Criteria
1. `POST /webhook` in `api/backend_source.py`:
   - Parses JSON body and verifies `secret` against `config.INTERVALS_WEBHOOK_SECRET` via `hmac.compare_digest`. Returns `401 Unauthorized` on mismatch.
   - Iterates through `events`:
     - Ignores events where `type != "ACTIVITY_UPLOADED"`.
     - Looks up athlete via `db.get_athlete(event['athlete_id'])`. If not found, skips gracefully.
     - Calls `db.save_activity(event['activity'], athlete_id, athlete_name, clubs)`.
   - Returns `200 OK` with `{"status": "ok", "processed": count, "saved": saved_count}`.
2. Unit tests in `tests/test_backend_source.py` verify valid webhook ingestion, invalid secret (`401`), duplicate idempotency, and unknown athlete handling.

#### Technical Tasks
- [ ] Implement `_handle_webhook()` in `api/backend_source.py` and wire route in local Flask runner.
- [ ] Write unit and E2E flow tests (Callback -> Webhook -> `GET /`) in `tests/test_backend_source.py`.

---

### Story 7: WireMock Setup (`DEV/QA` & `PRE`) + Demo Seeder & Simulator Scripts
- **As a** developer and product owner,
- **I want** portable WireMock stubs (for local Docker and WireMock Cloud) plus CLI scripts to seed `PRE` data and trigger live demo webhooks,
- **So that** I can test OAuth locally and run impressive, interactive live demos for prospective clients in `PRE`.

#### Acceptance Criteria
1. **WireMock Stubs (`mocks/`):**
   - `mocks/docker-compose.yml` starts `wiremock/wiremock` on `http://localhost:8089` mounting `./wiremock`.
   - `mocks/wiremock/mappings/oauth-token.json` stubs `POST /api/oauth/token` (returns realistic mock athlete token & profile for demo codes, and `400` for `code=invalid`).
   - Stubs are 100% compatible with importing into **WireMock Cloud (Free Tier)** for `PRE`.
   - `mocks/wiremock/mappings/oauth-authorize.json` stubs `GET /oauth/authorize` so clicking a demo registration link in `PRE` redirects straight to `/oauth/callback?code=demo_code_1&state={{request.query.state}}`!
2. **Demo Data Seeder (`scripts/seed_demo_data.py`):**
   - Populates target environment (`--env dev` or `--env pre`) with 12 realistic athletes and 50 varied activities (Run, Ride, Swim, Hike) so the `PRE` dashboard always looks active.
   - Supports `--reset` to wipe and restore `PRE` to a clean demo state before a client meeting.
3. **Live Webhook Simulator (`scripts/simulate_webhook.py`):**
   - Sends a valid `POST /webhook` payload to `DEV` (`localhost:5000`) or `PRE` (`ClubCounterAPI-PRE` URL) to demonstrate real-time leaderboard and kilometer updates live during a client call.

#### Technical Tasks
- [ ] Create `mocks/docker-compose.yml` and WireMock JSON mapping files (`oauth-authorize.json`, `oauth-token.json`).
- [ ] Create `scripts/seed_demo_data.py` with realistic Spanish club athlete names and activities.
- [ ] Create `scripts/simulate_webhook.py` CLI tool.
- [ ] Test local end-to-end flow against the local WireMock container.

---

### Story 8: 3-Environment CI/CD Pipelines & Branch Protection (`DEV/QA`, `PRE`, `PROD`)
- **As a** maintainer,
- **I want** automated GitHub Actions workflows for PR validation (`DEV/QA`), demo environment deployment (`PRE`), and production deployment (`PROD`),
- **So that** `master` is protected from direct pushes and `PRE` always reflects the latest stable demo build.

#### Acceptance Criteria
1. **`.github/workflows/ci-qa.yaml` (`DEV/QA`):**
   - Triggers on all Pull Requests targeting `pre` or `master`.
   - Runs `pytest tests/ -v` and spins up the WireMock Docker service container to verify the OAuth integration test.
2. **`.github/workflows/deploy-pre.yaml` (`PRE`):**
   - Triggers on push/merge to the `pre` branch.
   - Runs tests, packages `api/`, and deploys to AWS Lambda `ClubCounterAPI-PRE` (`eu-west-1`).
3. **`.github/workflows/deploy-prod.yaml` (`PROD`):**
   - Triggers on PR merge to `master` (protected branch).
   - Runs tests, packages `api/`, and deploys to AWS Lambda `ClubCounterAPI-PROD` (`eu-west-1`).
4. Documentation in `README.md` covers branch protection setup (`master` requires PR + green `ci-qa` status check) and Vercel environment setup (`PRE` vs `PROD`).

#### Technical Tasks
- [ ] Create `ci-qa.yaml`, `deploy-pre.yaml`, and `deploy-prod.yaml` in `.github/workflows/`.
- [ ] Provision `ATHLETES_PRE`, `ACTIVITIES_PRE`, `ATHLETES_PROD`, and `ACTIVITIES_PROD` in AWS DynamoDB (`eu-west-1`).
- [ ] Provision `ClubCounterAPI-PRE` and `ClubCounterAPI-PROD` Lambda functions and configure their environment variables.
- [ ] Document the 3-environment workflow and demo playbook in `README.md`.

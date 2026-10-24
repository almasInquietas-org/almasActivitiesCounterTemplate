---
name: wiremock-and-demo-env
description: >-
  Guides the creation and execution of WireMock stubs (local Docker for DEV/QA and
  WireMock Cloud Free Tier for PRE), demo database seeding (seed_demo_data.py), and
  live webhook simulation (simulate_webhook.py). Use when working on Story 7,
  mocks/, scripts/, or preparing a PRE environment demo.
---

# WireMock & PRE Demo Environment Skill

## 1. Architecture of Mocking (`DEV/QA` vs `PRE`)
- **Outbound OAuth (`api` → `Intervals.icu`):** Mocked via WireMock by setting `INTERVALS_OAUTH_BASE_URL`:
  - `DEV/QA`: `http://localhost:8089` (Docker `wiremock/wiremock:latest` with `--global-response-templating`)
  - `PRE`: `https://<mock-id>.wiremockapi.cloud` (WireMock Cloud Free Tier — 1,000 req/month free)
- **Inbound Data (`Intervals.icu` → `api` & DynamoDB):** Managed via `scripts/seed_demo_data.py` and `scripts/simulate_webhook.py`.

## 2. Portable WireMock Stub Format (`mocks/wiremock/mappings/`)
All JSON mapping files in `mocks/wiremock/mappings/` must be 100% compatible with both WireMock OSS and WireMock Cloud import:

### `oauth-authorize.json` (Simulates Intervals.icu Consent Redirect)
- Matches `GET /oauth/authorize` with query parameters `client_id`, `redirect_uri`, `state`.
- Returns `302 Found` with header:
  `Location: {{request.query.redirect_uri}}?code=demo_code_daniel&state={{request.query.state}}`
- Enables one-click registration demos in `DEV` and `PRE` without needing a real Intervals.icu account.

### `oauth-token.json` (Simulates Token Exchange)
- Stub 1 (Success): Matches `POST /api/oauth/token` when body contains `code=demo_code_` (or any valid demo code) → returns `200 OK` JSON with `access_token` and `athlete: {"id": "i_demo_01", "name": "Daniel Fernandez"}`.
- Stub 2 (Failure): Matches `POST /api/oauth/token` when body contains `code=invalid` → returns `400 Bad Request` `{"error": "invalid_grant"}`.

## 3. Demo Tooling Scripts (`scripts/`)

### `scripts/seed_demo_data.py`
- CLI flags:
  - `--env [dev|pre]` (selects `ATHLETES_DEV`/`ACTIVITIES_DEV` or `ATHLETES_PRE`/`ACTIVITIES_PRE`)
  - `--club <club_id>` (default `'almas_inquietas'`)
  - `--reset` (truncates existing items in the target environment tables before seeding; **refuses to run if table name ends with `_PROD`** as a safety guard!).
- Seeds 12 realistic athletes and 40–50 varied activities (`Run`, `Ride`, `Swim`, `Hike`, `Walk`) with recent ISO timestamps over the past 14 days so the dashboard progress bar, checkpoints, leaderboard medals (🥇🥈🥉), and activity carousel look vibrant for client demos.

### `scripts/simulate_webhook.py`
- CLI flags:
  - `--url <target_api_url>` (e.g., `http://127.0.0.1:5000` or the `ClubCounterAPI-PRE` Function URL)
  - `--secret <webhook_secret>`
  - `--athlete-id <id>` (default `'i_demo_01'`)
  - `--name <activity_title>` (default `'Entreno en directo (Demo)'`)
  - `--type [Run|Ride|Swim|Hike|Walk]` (default `'Run'`)
  - `--km <float>` (default `12.5`)
- Sends `POST {url}/webhook` with a unique `activity.id` (`int(time.time())`) and prints the HTTP status and response so a presenter can trigger a live update during a client call.

# Architecture & Implementation Plan: New Repo (Intervals.icu Edition)

## 1. Context & Clean-Slate Advantage

Since the previous Strava-based project was a Proof of Concept (POC) that has concluded, **we are starting a fresh repository with zero legacy constraints**.

Starting clean in a new repository unlocks major simplifications:
1. **No Worker Lambda or EventBridge:** The new repo starts without a polling worker. All data ingestion happens via **Intervals.icu Webhooks** (`POST /webhook`) directly on the API Lambda.
2. **Only 2 DynamoDB Tables per Environment (Unified Athlete Table):**
   - Instead of maintaining 3 separate tables (activities, users, and tokens), we only need **2 clean tables**:
     1. **`ATHLETES_<ENV>`**: Keyed by unique `athlete_id` (solves the old Strava name-collision bug!) storing OAuth tokens, display name, and club memberships.
     2. **`ACTIVITIES_<ENV>`**: Keyed by real `activity_id` from Intervals.icu, tagged with `athlete_id`, `athlete_name`, and `clubs`.
3. **Native Multi-Club Support via OAuth `state`:**
   - Each club gets a dedicated registration link (`...&state=club_id`).
   - Every activity saved via webhook is tagged with the athlete's `clubs`, allowing the dashboard to show either the global sum across all clubs or filter by a specific club (`GET /?club=club_id`).
4. **3 Isolated Environments (`DEV/QA`, `PRE`, `PROD`):**
   - Full lifecycle separation from local WireMock testing (`DEV/QA`), to an always-on client demo environment with realistic mock data (`PRE`), to live public usage (`PROD`).

> [!WARNING]
> **Device Requirement for Club Members (PROD):** Intervals.icu does **not** trigger webhooks or expose API data for activities synced *from Strava*. Club members must connect their device platform (**Garmin, Coros, Polar, Suunto, Wahoo**) directly to their free Intervals.icu account, or upload `.FIT`/`.GPX` files directly.

---

## 2. Multi-Environment Strategy (`DEV/QA`, `PRE`, `PROD`)

### 2.1 Same AWS Region (`eu-west-1`) vs. Different Regions

**Recommendation: Keep all environments in the SAME region (`eu-west-1`) using environment suffixes (`_PRE`, `_PROD`).**

Why **not** separate AWS regions?
- **AWS Free Tier is per-account, NOT per-region:** AWS calculates your free 25 GB of DynamoDB storage and 1M Lambda invocations across all regions combined. Splitting across regions does not give extra free tier quota.
- **Zero Console Confusion:** Keeping everything in `eu-west-1` lets you see `ClubCounterAPI-PRE` and `ClubCounterAPI-PROD` side by side without accidentally deploying to or debugging the wrong region.
- **Lowest Latency:** Both your `PRE` client demos and `PROD` users are in Europe, so `eu-west-1` (Ireland) gives optimal response times for both.

### 2.2 Environment Matrix

| Dimension | 1. `DEV / QA` | 2. `PRE` (Pre-Production / Demo) | 3. `PROD` (Production) |
|---|---|---|---|
| **Purpose** | Implementing & testing stories before merge | Always-on stable showcase with mock data for client demos | Live public platform with real club data |
| **Git Branch** | `feature/*` & Pull Requests | `pre` (or automatic on PR merge before release) | `master` (Protected — PR only, no direct push) |
| **Backend Compute** | Local Flask (`:5000`) + GitHub Actions CI runner | AWS Lambda `ClubCounterAPI-PRE` | AWS Lambda `ClubCounterAPI-PROD` |
| **DynamoDB Tables** | Local `moto` / DynamoDB Local | `ATHLETES_PRE`<br>`ACTIVITIES_PRE` | `ATHLETES_PROD`<br>`ACTIVITIES_PROD` |
| **Intervals OAuth URL** | Local **WireMock Docker** (`http://localhost:8089`) | **WireMock Cloud** Free Tier (`https://<id>.wiremockapi.cloud`) | Real Intervals.icu (`https://intervals.icu`) |
| **Activity Ingestion** | Local CLI webhook simulator & `pytest` | Pre-seeded realistic dataset + Demo Webhook Simulator script | Real Intervals.icu Webhooks |
| **Frontend Hosting** | `localhost:5173` (Vite dev) | Vercel Preview (`pre-almasactivitiescounter.vercel.app`) | Vercel Production (`almasactivitiescounter.vercel.app`) |

---

## 3. Mocking Strategy for `DEV/QA` and `PRE`

In our architecture, there are **two flows** to mock for testing and client demos:
1. **Outbound HTTP calls (API → Intervals.icu):** When an athlete clicks a registration link, our Lambda sends `POST /api/oauth/token` to exchange the `code` for an `access_token` and athlete profile.
2. **Inbound data (Intervals.icu → API & DynamoDB):** Populating the dashboard with realistic club data and simulating live incoming `POST /webhook` workout events during a client demo.

### 3.1 Mocking Outbound OAuth Calls with WireMock (Free)

By making `INTERVALS_OAUTH_BASE_URL` an environment variable in `api_config.py` (defaulting to `https://intervals.icu`), our Lambda code never changes between environments—only the URL changes:

- **In `DEV/QA` (Local & GitHub Actions):**
  - Use **WireMock OSS via Docker** (`docker compose up wiremock` on port `8089`).
  - Stub files live in the repo under `mocks/wiremock/mappings/oauth-token.json`.
  - Maps `code=mock_code_daniel` → returns athlete `"Daniel Fernandez"`, `code=mock_code_error` → returns `400 Bad Request`.
- **In `PRE` (Cloud Demo Environment):**
  - Options for hosting the WireMock server in the cloud for free:
    1. **WireMock Cloud (Free Forever Tier) ⭐ Recommended:** Includes 3 mock APIs and **1,000 requests/month for free**. Since our Lambda only calls WireMock when you click the registration link during a demo, 1,000 calls/month is plenty and requires zero server maintenance. We import the exact same `mocks/wiremock/mappings/` JSON file from our repo.
    2. **Self-Hosted Free Alternative (Render.com / Fly.io Free Container or Built-in `/mock/intervals` route):** If you ever exceed 1,000 OAuth demo clicks/month, you can deploy the `wiremock/wiremock` Docker image to a free Render.com web service, or point `INTERVALS_OAUTH_BASE_URL` to a mock route inside the PRE Lambda itself (`$0` forever).

### 3.2 Mocking Inbound Data & Live Demos in `PRE` (`scripts/`)

Because WireMock is a passive server (it waits to be called), we complement it with two lightweight scripts in `scripts/` for `PRE` and `DEV/QA`:
1. **`scripts/seed_demo_data.py`:**
   - Populates `ATHLETES_PRE` and `ACTIVITIES_PRE` with a curated, realistic dataset (e.g., 12 club athletes, 50 activities across Run/Ride/Swim/Hike, progress at ~78% toward the goal) so the `PRE` URL is **always ready to show clients at a moment's notice**.
   - Can be reset anytime with `python scripts/seed_demo_data.py --env pre --reset`.
2. **`scripts/simulate_webhook.py`:**
   - Fires a signed `POST /webhook` (`ACTIVITY_UPLOADED`) request to either `localhost:5000` (`DEV`) or `ClubCounterAPI-PRE` (`PRE`).
   - During a live client demo, you can run `python scripts/simulate_webhook.py --env pre --athlete "Laura M." --km 15.4 --type Run` and watch the PRE dashboard counter and leaderboard update live on screen!

---

## 4. Repository Structure (New Repo)

```
almasActivitiesCounterTemplate/
├── .github/workflows/
│   ├── ci-qa.yaml                # Runs on PRs: pytest + WireMock integration tests
│   ├── deploy-pre.yaml           # Deploys to ClubCounterAPI-PRE on push/merge to `pre` branch
│   └── deploy-prod.yaml          # Deploys to ClubCounterAPI-PROD on merge to `master`
│
├── api/                          # Single Backend Lambda (API + OAuth + Webhooks)
│   ├── backend_source.py         # Routes: GET /, POST /auth/token, GET /oauth/callback, POST /webhook
│   ├── api_config.py             # Env vars (including INTERVALS_OAUTH_BASE_URL)
│   ├── auth.py                   # Frontend HMAC + Bearer token verification
│   ├── intervals_oauth.py        # OAuth code exchange & HTML confirmation page
│   ├── rate_limiter.py           # Sliding window rate limiter per IP
│   ├── db.py                     # DynamoDB operations (Athletes & Activities tables)
│   ├── services.py               # Dashboard aggregation, filtering & leaderboard calculation
│   └── utils.py                  # DecimalEncoder
│
├── mocks/                        # WireMock OSS & WireMock Cloud stub definitions
│   ├── docker-compose.yml        # Spins up local WireMock on :8089 for DEV/QA
│   └── wiremock/
│       └── mappings/
│           ├── oauth-authorize.json
│           └── oauth-token.json
│
├── scripts/                      # Demo & QA tooling
│   ├── seed_demo_data.py         # Resets & seeds realistic mock data into PRE (or local)
│   └── simulate_webhook.py       # Sends signed ACTIVITY_UPLOADED webhooks to DEV or PRE
│
├── frontend/                     # React Dashboard (deployed to Vercel PRE & PROD)
│   └── ...
│
├── tests/                        # Pytest + Moto unit & integration suite
│   └── ...
│
├── .gitignore
└── README.md
```

---

## 5. DynamoDB Schema (Per Environment)

### Table 1: `ATHLETES_PRE` / `ATHLETES_PROD`
**Partition Key:** `athlete_id` (String — Intervals.icu ID, e.g., `"i2049151"`)

| Field | Type | Description |
|---|---|---|
| `athlete_id` | String (PK) | Unique Intervals.icu athlete ID |
| `athlete_name` | String | Full display name (e.g., `"Daniel Fernandez"`) |
| `clubs` | List of Strings | Clubs the athlete has joined (`["almas_inquietas"]`) |
| `access_token` | String | OAuth Bearer token |
| `updated_at` | String | ISO 8601 timestamp |

### Table 2: `ACTIVITIES_PRE` / `ACTIVITIES_PROD`
**Partition Key:** `activity_id` (String — Intervals.icu activity ID, e.g., `"48566307"`)

| Field | Type | Description |
|---|---|---|
| `activity_id` | String (PK) | Native unique activity ID |
| `athlete_id` | String | Reference to `athlete_id` |
| `athlete` | String | Athlete display name |
| `clubs` | List of Strings | Snapshot of athlete's clubs (`["almas_inquietas"]`) |
| `title` | String | Activity name (e.g., `"Morning Run"`) |
| `type` | String | Activity type (`"Run"`, `"Ride"`, `"Swim"`, etc.) |
| `sport_type` | String | Sport subtype |
| `distance_km` | Number (Decimal) | Distance in km (`distance / 1000` rounded to 2 decimals) |
| `moving_time_seconds` | Number (Int) | Moving time in seconds |
| `total_elevation_gain` | Number (Decimal) | Elevation gain in meters |
| `start_date` | String | ISO 8601 local timestamp (`start_date_local`) |

---

## 6. Full API & Frontend Contract (Self-Contained Spec for Empty Repo)

With the exact specifications below, **you do NOT need any backend code from the old POC repository**. A brand-new repository only needs the `frontend/` folder plus `MIGRATION_PLAN.md` and `MIGRATION_STORIES.md`.

### 6.1 Frontend Auth Contract (`POST /auth/token` & `api/auth.py`)
The existing `frontend/src/apiAuth.js` uses a two-step HMAC-SHA256 → Bearer token flow:
- **Passthrough Mode:** If `API_KEY` or `API_SIGNING_SECRET` are empty strings, auth is disabled. `POST /auth/token` returns `200 {"token": "passthrough", "ttl": 999999}` and `GET /` does not require a `Bearer` token.
- **When Enabled:**
  1. `POST /auth/token` reads headers `x-api-key`, `x-timestamp`, `x-nonce`, `x-signature`.
  2. Checks `x-api-key == config.API_KEY` and `abs(time.time() - float(timestamp)) <= config.AUTH_TOLERANCE_SECONDS` (default `300`).
  3. Computes `HMAC-SHA256(API_SIGNING_SECRET, f"{timestamp}.{nonce}").hexdigest()` and compares with `x-signature` via `hmac.compare_digest`.
  4. Generates a UUIDv4 token stored in memory (`_active_tokens[token] = time.time() + TOKEN_TTL_SECONDS`, default `300`) and returns `200 {"token": token, "ttl": 300}` (or `401` on failure).
  5. `GET /` verifies header `Authorization: Bearer <token>` exists in `_active_tokens` and is not expired.

### 6.2 Rate Limiter (`api/rate_limiter.py`)
- Sliding window per client IP: keeps timestamps in `_request_history[ip]` within `now - RATE_LIMIT_WINDOW` (default `60`s). Blocks with `429 Too Many Requests` if `len(history) >= RATE_LIMIT_MAX` (default `30`).

### 6.3 Club Registration Callback (`GET /oauth/callback`)
- Club share link:
  `{INTERVALS_OAUTH_BASE_URL}/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={LAMBDA_URL}/oauth/callback&scope=ACTIVITY:READ&state={CLUB_ID}`
- Exchanges `code` via `POST {INTERVALS_OAUTH_BASE_URL}/api/oauth/token` (`application/x-www-form-urlencoded`: `client_id`, `client_secret`, `code`).
- Saves `athlete_id`, `athlete_name`, `access_token`, and appends `state` (`club_id`) to `clubs` in `ATHLETES_<ENV>`.
- Returns `200 OK` (`Content-Type: text/html`) confirmation page.

### 6.4 Webhook Receiver (`POST /webhook`)
- Verifies JSON body `payload.get("secret") == config.INTERVALS_WEBHOOK_SECRET` via `hmac.compare_digest` (returns `401` if invalid).
- For each event in `payload.get("events", [])` where `event["type"] == "ACTIVITY_UPLOADED"`:
  - Looks up `event["athlete_id"]` in `ATHLETES_<ENV>`. If unknown, skips.
  - Saves `event["activity"]` to `ACTIVITIES_<ENV>` with `ConditionExpression="attribute_not_exists(activity_id)"`.
- Returns `200 OK` `{"status": "ok", "processed": N, "saved": M}`.

### 6.5 Dashboard Data Contract (`GET /`)
`frontend/src/App.jsx` expects `GET /` to return this exact JSON structure:
```json
{
  "total_km": 1234.56,
  "total_activities": 45,
  "top_athletes": [
    {
      "athlete_name": "Daniel Fernandez",
      "currentKm": 123.45,
      "lastIncrement": 10.5
    }
  ],
  "last_activities": [
    {
      "id": "48566307",
      "title": "Morning Run",
      "athlete": "Daniel Fernandez",
      "type": "Run",
      "sport_type": "Run",
      "distance_km": 10.03,
      "moving_time_seconds": 3643,
      "date": "2026-10-24T06:30:00"
    }
  ],
  "config": {
    "goal_km": 5000.0,
    "title": "Rides the Wave",
    "checkpoints": [1000.0, 2500.0, 4000.0]
  }
}
```
> **Contract notes:**
> - `top_athletes`: Grouped by `athlete_id` (max 10, sorted by `currentKm` descending). `lastIncrement` is the `distance_km` of that athlete's most recent activity.
> - `last_activities`: Sorted by `date` (`start_date`) descending, sliced to `config.LAST_ACT` (default `10`).
> - `config.goal_km`: Float if `GOAL_KM` env var is set, or `null` if unset/empty (hides the progress bar in the frontend).
> - `config.checkpoints`: Sorted list of floats parsed from comma-separated `CHECKPOINTS` env var (empty list `[]` if `goal_km` is `null`).

---

## 7. Environment Variables (`ClubCounterAPI-PRE` & `ClubCounterAPI-PROD`)

| Variable | `DEV / QA` Default | `PRE` Value | `PROD` Value |
|---|---|---|---|
| `AWS_REGION` | `eu-west-1` | `eu-west-1` | `eu-west-1` |
| `ATHLETES_TABLE_NAME` | `ATHLETES_DEV` | `ATHLETES_PRE` | `ATHLETES_PROD` |
| `ACTIVITIES_TABLE_NAME` | `ACTIVITIES_DEV` | `ACTIVITIES_PRE` | `ACTIVITIES_PROD` |
| `INTERVALS_OAUTH_BASE_URL` | `http://localhost:8089` | `https://<mock>.wiremockapi.cloud` | `https://intervals.icu` |
| `INTERVALS_CLIENT_ID` | `dev-client-id` | `pre-demo-client-id` | `<real-client-id>` |
| `INTERVALS_CLIENT_SECRET` | `dev-secret` | `pre-demo-secret` | `<real-client-secret>` |
| `INTERVALS_WEBHOOK_SECRET` | `dev-webhook-secret` | `pre-webhook-secret` | `<real-webhook-secret>` |
| `GOAL_KM` | `500` | `5000` | `<club-goal>` |
| `LAST_ACT` | `10` | `10` | `10` |

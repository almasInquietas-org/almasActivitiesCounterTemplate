---
name: intervals-icu-integration
description: Expert specification for integrating with the Intervals.icu REST API v1, OAuth2 multi-user authentication, webhook ingestion, PMC analytics, and the Intervals Workout Builder DSL. Use whenever building, debugging, or querying Intervals.icu endpoints, models, or training workflows.
---

# Intervals.icu Integration Skill

## 1. Base Configuration & HTTP Client Rules
- **Base URL:** `https://intervals.icu/api/v1`
- **OpenAPI 3.0 Spec:** `https://intervals.icu/api/v1/docs`
- **Cloudflare User-Agent Requirement:** NEVER use default HTTP client headers (e.g., `python-requests`, `urllib`, `axios`, `node-fetch`). Cloudflare blocks generic User-Agents with `403 Forbidden`. Always set a custom `User-Agent: <AppName>/<Version> (Integration)` header on every request.
- **Rate Limiting:** Maximum **10 requests/second per IP** (bursts above this drop connections or return `429 Too Many Requests`). Enforce a minimum `100ms` delay or token-bucket limiter (8 req/s safe ceiling) and respect `Retry-After` headers.
- **Schema Tolerance:** Never enforce `additionalProperties: false` or strict deserialization on API responses. Intervals.icu regularly adds new computed fields to `Activity`, `Wellness`, and `Athlete` payloads without versioning the `/v1` path.

## 2. Authentication & OAuth 2.0 Flows
### Registered App OAuth2 (Production Multi-User)
- **Authorize URL:** `GET https://intervals.icu/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPES}&state={STATE}`
- **Token Exchange:** `POST https://intervals.icu/api/oauth/token`
  - `Content-Type: application/x-www-form-urlencoded`
  - Body: `client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={CODE}`
  - Returns: `{"access_token": "...", "token_type": "Bearer", "scope": "...", "athlete": {"id": "i12345", "name": "..."}}`
- **Header:** `Authorization: Bearer <access_token>`
- **Disconnect App:** `DELETE https://intervals.icu/api/v1/disconnect-app`
- **Critical Token Architecture Rules:**
  1. **No Refresh Tokens:** Access tokens do not expire on a short TTL and there is no `refresh_token` grant.
  2. **Single Active Token Invalidation:** Triggering a new OAuth authorization flow for a user **immediately invalidates** their existing access token. Persist tokens in a centralized database keyed by `athlete.id` and share across user sessions/devices.
  3. **Athlete ID Shorthand:** You can pass `0` as the `{id}` parameter (e.g., `/api/v1/athlete/0/activities`) to automatically target the owner of the current Bearer token or API Key.

### Personal API Key (Local Dev / Single User)
- **Header:** `Authorization: Basic <base64("API_KEY:" + api_key)>`

### Scopes (`READ` or `WRITE`, comma-separated, no spaces)
- `ACTIVITY:READ`, `ACTIVITY:WRITE`
- `WELLNESS:READ`, `WELLNESS:WRITE`
- `CALENDAR:READ`, `CALENDAR:WRITE`
- `LIBRARY:READ`, `LIBRARY:WRITE`
- `SETTINGS:READ`, `SETTINGS:WRITE`
- `CHATS:READ`, `CHATS:WRITE`

## 3. Core Endpoints & Batch Patterns
Always prefer bulk and date-range endpoints over single-item loops. Dates use `YYYY-MM-DD` or ISO-8601 (`YYYY-MM-DDTHH:mm:ss`).

### Athlete & Settings
- `GET /api/v1/athlete/{id}/profile` — Athlete summary, sport settings, zones, FTP, LTHR.
- `PUT /api/v1/athlete/{id}/sport-settings/{type}` — Update FTP, LTHR, threshold pace, or zones for a sport (`Ride`, `Run`, `Swim`).

### Activities & Streams
- `GET /api/v1/athlete/{id}/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD` — List activities.
  - **Note:** Activities imported directly from Strava have stub payloads (`icu_training_load` and streams stripped) due to Strava API terms. Direct integrations (Garmin, Wahoo, Zwift, Hammerhead, Coros, Suunto, `.fit` upload) return full data.
- `GET /api/v1/activity/{activityId}?intervals=true` — Full activity details + detected interval/lap summary.
- `GET /api/v1/activity/{activityId}/streams.json?types=watts,heartrate,cadence,altitude,latlng,velocity_smooth,temp,time` — High-frequency time-series arrays.
- `POST /api/v1/athlete/{id}/activities` — `multipart/form-data` with `file` (`.fit`, `.tcx`, `.gpx`, `.gz`) and optional query params `name`, `description`, `external_id`.

### Wellness & PMC Metrics
- `GET /api/v1/athlete/{id}/wellness?oldest=YYYY-MM-DD&newest=YYYY-MM-DD`
- `PUT /api/v1/athlete/{id}/wellness-bulk` — Accepts JSON array of wellness records:
  ```json
  [
    {
      "id": "2026-11-06",
      "weight": 71.5,
      "restingHR": 46,
      "hrv": 78.4,
      "sleepSecs": 28800,
      "sleepScore": 86,
      "fatigue": 2,
      "mood": 1,
      "motivation": 1,
      " soreness": 2
    }
  ]
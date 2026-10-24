---
name: intervals-webhook-oauth
description: >-
  Reference specification and implementation patterns for Intervals.icu OAuth 2.0
  token exchange, club registration links using the state parameter, and real-time
  ACTIVITY_UPLOADED webhook ingestion. Use when working on api/intervals_oauth.py,
  GET /oauth/callback, or POST /webhook.
---

# Intervals.icu OAuth 2.0 & Webhook Integration Skill

## 1. Club Registration Link Format
Each club receives a dedicated registration URL with its identifier in the `state` parameter:
```text
{INTERVALS_OAUTH_BASE_URL}/oauth/authorize?client_id={INTERVALS_CLIENT_ID}&redirect_uri={LAMBDA_URL}/oauth/callback&scope=ACTIVITY:READ&state={CLUB_ID}
```

When the athlete approves, Intervals.icu redirects to:
```text
GET /oauth/callback?code={AUTH_CODE}&state={CLUB_ID}
```
If the athlete declines:
```text
GET /oauth/callback?error=access_denied&state={CLUB_ID}
```

## 2. Token Exchange (`POST {INTERVALS_OAUTH_BASE_URL}/api/oauth/token`)
- **Zero-Dependency Rule:** Use `urllib.request.Request` and `urllib.parse.urlencode` (never `requests`).
- **Request:**
  - Method: `POST`
  - Header: `Content-Type: application/x-www-form-urlencoded`
  - Form fields:
    - `client_id`: `config.INTERVALS_CLIENT_ID`
    - `client_secret`: `config.INTERVALS_CLIENT_SECRET`
    - `code`: authorization code from query string
- **Expected 200 OK JSON Response from Intervals.icu:**
  ```json
  {
    "token_type": "Bearer",
    "access_token": "e9a8b7c6...",
    "scope": "ACTIVITY:READ",
    "athlete": {
      "id": "i2049151",
      "name": "Daniel Fernandez"
    }
  }
  ```
- **HTML Confirmation Response:**
  - Always sanitize `athlete_name`, `club_id`, and `error_msg` with `html.escape()` before interpolating into HTML.
  - Return `Content-Type: text/html; charset=utf-8` in the Lambda response headers.

## 3. Webhook Ingestion (`POST /webhook`)
Intervals.icu sends a `POST` request with the following JSON structure:
```json
{
  "secret": "configured_webhook_secret",
  "events": [
    {
      "athlete_id": "i2049151",
      "type": "ACTIVITY_UPLOADED",
      "timestamp": "2026-10-24T06:40:47.011+00:00",
      "activity": {
        "id": 48566307,
        "start_date_local": "2026-10-24T06:30:00",
        "type": "Ride",
        "name": "Morning Ride",
        "moving_time": 3600,
        "distance": 30000,
        "total_elevation_gain": 250
      }
    }
  ]
}
```

### Security & Processing Rules
1. **Secret Verification:**
   - Extract `secret = str(payload.get('secret') or '')`.
   - Compare with `config.INTERVALS_WEBHOOK_SECRET` using `hmac.compare_digest(secret, config.INTERVALS_WEBHOOK_SECRET)`.
   - If `config.INTERVALS_WEBHOOK_SECRET` is empty or does not match, return `401 Unauthorized`.
2. **Event Filtering & Lookup:**
   - Only process events where `event.get('type') == 'ACTIVITY_UPLOADED'` and `event.get('activity')` is a dict.
   - Look up `athlete = db.get_athlete(str(event.get('athlete_id') or ''))`.
   - If `athlete is None`, skip the event (do not fail the batch).
   - Call `db.save_activity(activity=event['activity'], athlete_id=athlete['athlete_id'], athlete_name=athlete['athlete_name'], clubs=athlete.get('clubs', []))`.
3. **Response:**
   - Return `200 OK` with `{"status": "ok", "processed": processed_count, "saved": saved_count}`.

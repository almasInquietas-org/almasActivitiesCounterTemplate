"""
backend_source.py - AWS Lambda Function URL Router & Local Dev Server.

Routes:
  - GET  /               -> Dashboard data (JSON)
  - POST /auth/token     -> HMAC-SHA256 handshake for frontend Bearer token
  - GET  /oauth/callback -> Intervals.icu OAuth callback & athlete registration (HTML)
  - POST /webhook        -> Ingestion of real-time ACTIVITY_UPLOADED webhooks
"""
import base64
import hmac
import json
from typing import Any

from api import api_config as config
from api import auth
from api import db
from api import intervals_oauth
from api import rate_limiter
from api import services
from api.intervals_oauth import OAuthError
from api.utils import DecimalEncoder


def _make_cors_headers(origin: str | None = None) -> dict[str, str]:
    """Generates CORS headers based on request origin and config."""
    allowed = config.CORS_ALLOWED_ORIGINS or ["*"]
    header_val = "*"
    if "*" not in allowed and origin:
        if origin in allowed:
            header_val = origin
        else:
            header_val = allowed[0]

    return {
        "Access-Control-Allow-Origin": header_val,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key,x-timestamp,x-nonce,x-signature",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def _make_response(status_code: int, body_dict: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
    """Helper to create standardized JSON responses."""
    headers = {
        "Content-Type": "application/json",
        **_make_cors_headers(origin),
    }
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body_dict, cls=DecimalEncoder),
    }


def _make_html_response(status_code: int, html_body: str, origin: str | None = None) -> dict[str, Any]:
    """Helper to create standardized HTML responses."""
    headers = {
        "Content-Type": "text/html; charset=utf-8",
        **_make_cors_headers(origin),
    }
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": html_body,
    }


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Extract method, path, query parameters, headers, client IP, and decoded body
    from both Lambda Function URL v1.0 and v2.0 payloads.
    """
    request_ctx = event.get("requestContext") or {}
    http_ctx = request_ctx.get("http") or {}

    # Method
    method = http_ctx.get("method") or event.get("httpMethod") or "GET"
    method = method.upper()

    # Path
    path = event.get("rawPath") or event.get("path") or "/"

    # Query string parameters
    query_params = event.get("queryStringParameters") or {}

    # Headers (normalized to lowercase keys)
    raw_headers = event.get("headers") or {}
    headers = {str(k).lower(): str(v) for k, v in raw_headers.items()}

    # Client IP
    client_ip = (
        http_ctx.get("sourceIp")
        or request_ctx.get("identity", {}).get("sourceIp")
        or "0.0.0.0"
    )

    # Body decoding
    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(raw_body).decode("utf-8")
        except Exception:
            body = str(raw_body)
    else:
        body = str(raw_body)

    return {
        "method": method,
        "path": path,
        "query_params": query_params,
        "headers": headers,
        "client_ip": client_ip,
        "body": body,
    }


def _handle_oauth_callback(query_params: dict[str, str], origin: str | None = None) -> dict[str, Any]:
    """
    Handles GET /oauth/callback.
    1. Checks for error=access_denied or missing code -> 400 HTML response.
    2. Exchanges code for access token via Intervals.icu OAuth endpoint.
    3. Saves athlete to DynamoDB (deduplicating club_id).
    4. Returns 200 OK HTML confirmation page.
    """
    club_id = query_params.get("state") or "default"
    error_param = query_params.get("error")
    code = query_params.get("code")

    if error_param == "access_denied":
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg="Access was denied by the user. Authorization was cancelled.",
        )
        return _make_html_response(400, html, origin)

    if not code:
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg="Missing authorization code in callback parameters.",
        )
        return _make_html_response(400, html, origin)

    try:
        token_data = intervals_oauth.exchange_code_for_token(code)
    except OAuthError as err:
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=str(err),
        )
        return _make_html_response(400, html, origin)
    except Exception as err:
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=f"Unexpected authorization error: {err}",
        )
        return _make_html_response(500, html, origin)

    # Save athlete to database
    athlete_id = token_data["athlete_id"]
    athlete_name = token_data["athlete_name"]
    access_token = token_data["access_token"]

    db.save_athlete(
        athlete_id=athlete_id,
        athlete_name=athlete_name,
        access_token=access_token,
        club_id=club_id,
    )

    html = intervals_oauth.render_callback_html(
        success=True,
        athlete_name=athlete_name,
        club_id=club_id,
    )
    return _make_html_response(200, html, origin)


def _handle_webhook(body_str: str, origin: str | None = None) -> dict[str, Any]:
    """
    Handles POST /webhook.
    1. Parses JSON payload.
    2. Verifies secret against config.INTERVALS_WEBHOOK_SECRET using hmac.compare_digest.
    3. Iterates over events:
       - Only processes event['type'] == 'ACTIVITY_UPLOADED' with a dict activity.
       - Looks up athlete via db.get_athlete(athlete_id). Skips if not found.
       - Saves activity via db.save_activity(event['activity'], athlete_id, athlete_name, clubs).
    4. Returns 200 OK {"status": "ok", "processed": processed_count, "saved": saved_count}.
    """
    if not body_str:
        return _make_response(400, {"error": "Malformed JSON: empty body"}, origin)

    try:
        payload = json.loads(body_str)
    except Exception as e:
        return _make_response(400, {"error": f"Malformed JSON: {e}"}, origin)

    if not isinstance(payload, dict):
        return _make_response(400, {"error": "Malformed JSON: payload must be a JSON object"}, origin)

    secret = str(payload.get("secret") or "")
    configured_secret = str(config.INTERVALS_WEBHOOK_SECRET or "")

    # If webhook secret is empty/unset in config or does not match payload secret -> 401
    if not configured_secret or not hmac.compare_digest(secret, configured_secret):
        return _make_response(401, {"error": "Unauthorized"}, origin)

    events = payload.get("events")
    if not isinstance(events, list):
        events = []

    processed_count = 0
    saved_count = 0

    for event in events:
        if not isinstance(event, dict):
            continue

        if event.get("type") != "ACTIVITY_UPLOADED":
            continue

        activity_data = event.get("activity")
        if not isinstance(activity_data, dict):
            continue

        processed_count += 1

        raw_athlete_id = event.get("athlete_id")
        if not raw_athlete_id:
            continue
        athlete_id = str(raw_athlete_id)

        athlete = db.get_athlete(athlete_id)
        if not athlete:
            # Unknown athlete registered elsewhere or deleted, skip gracefully
            continue

        athlete_name = athlete.get("athlete_name", "Unknown Athlete")
        clubs = athlete.get("clubs", [])

        is_new = db.save_activity(
            activity=activity_data,
            athlete_id=athlete_id,
            athlete_name=athlete_name,
            clubs=clubs,
        )
        if is_new:
            saved_count += 1

    return _make_response(
        200,
        {
            "status": "ok",
            "processed": processed_count,
            "saved": saved_count,
        },
        origin,
    )


def _handle_auth_token(headers: dict[str, str], origin: str | None = None) -> dict[str, Any]:
    """
    Handles POST /auth/token.
    Performs HMAC-SHA256 handshake or passthrough if auth disabled.
    """
    if not auth.is_auth_enabled():
        return _make_response(200, {"token": "passthrough", "ttl": 999999}, origin)

    api_key = headers.get("x-api-key", "")
    timestamp = headers.get("x-timestamp", "")
    nonce = headers.get("x-nonce", "")
    signature = headers.get("x-signature", "")

    if not auth.verify_signature(api_key, timestamp, nonce, signature):
        return _make_response(401, {"error": "Invalid signature or expired request"}, origin)

    token, ttl = auth.generate_token()
    return _make_response(200, {"token": token, "ttl": ttl}, origin)


def _handle_dashboard(
    headers: dict[str, str],
    query_params: dict[str, str],
    origin: str | None = None,
) -> dict[str, Any]:
    """
    Handles GET /.
    Verifies Bearer token if auth enabled and returns aggregated dashboard data.
    """
    if auth.is_auth_enabled():
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return _make_response(401, {"error": "Missing or invalid Authorization header"}, origin)
        token = auth_header[7:].strip()
        if not auth.verify_token(token):
            return _make_response(401, {"error": "Invalid or expired Bearer token"}, origin)

    club_param = query_params.get("club")
    data = services.build_dashboard_data(club_filter=club_param)
    return _make_response(200, data, origin)


def process_activities(event: dict[str, Any], context: object = None) -> dict[str, Any]:
    """
    Main AWS Lambda entry point for Function URLs.
    Dispatches requests to corresponding handler functions.
    """
    parsed = _parse_event(event)
    method = parsed["method"]
    path = parsed["path"].rstrip("/")
    if not path:
        path = "/"

    origin = parsed["headers"].get("origin")
    client_ip = parsed["client_ip"]

    # Rate limiting check
    if rate_limiter.is_rate_limited(client_ip):
        return _make_response(429, {"error": "Too Many Requests"}, origin)

    # Handle CORS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": _make_cors_headers(origin),
            "body": "",
        }

    # Route: GET /oauth/callback
    if method == "GET" and path == "/oauth/callback":
        return _handle_oauth_callback(parsed["query_params"], origin)

    # Route: POST /webhook
    if method == "POST" and path == "/webhook":
        return _handle_webhook(parsed["body"], origin)

    # Route: POST /auth/token
    if method == "POST" and path == "/auth/token":
        return _handle_auth_token(parsed["headers"], origin)

    # Route: GET /
    if method == "GET" and path == "/":
        return _handle_dashboard(parsed["headers"], parsed["query_params"], origin)

    # 404 Fallback for unhandled routes
    return _make_response(404, {"error": "Not Found", "path": path, "method": method}, origin)


if __name__ == "__main__":
    # Local Flask development runner
    from flask import Flask, make_response, request

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "OPTIONS"])
    @app.route("/<path:path>", methods=["GET", "POST", "OPTIONS"])
    def local_route(path: str):
        full_path = "/" + path if path else "/"
        raw_headers = {k: v for k, v in request.headers.items()}
        raw_query = {k: v for k, v in request.args.items()}

        mock_event = {
            "rawPath": full_path,
            "queryStringParameters": raw_query,
            "headers": raw_headers,
            "body": request.get_data(as_text=True),
            "isBase64Encoded": False,
            "requestContext": {
                "http": {
                    "method": request.method,
                    "path": full_path,
                    "sourceIp": request.remote_addr or "127.0.0.1",
                }
            },
        }

        res = process_activities(mock_event, None)
        flask_res = make_response(res["body"], res["statusCode"])
        for h_k, h_v in res.get("headers", {}).items():
            flask_res.headers[h_k] = h_v
        return flask_res

    print("Starting local development server on http://localhost:8080...")
    app.run(host="0.0.0.0", port=8080, debug=True)

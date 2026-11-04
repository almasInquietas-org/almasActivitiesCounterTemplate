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
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Ensure compatibility when packaged directly at the root of an AWS Lambda zip
if 'api' not in sys.modules:
    import types
    _api_pkg = types.ModuleType('api')
    _api_pkg.__path__ = [str(Path(__file__).resolve().parent)]
    sys.modules['api'] = _api_pkg

from api import api_config as config
from api import auth
from api import db
from api import intervals_oauth
from api import rate_limiter
from api import services
from api.intervals_oauth import OAuthError
from api.utils import DecimalEncoder

# Configure root and module loggers so AWS Lambda CloudWatch captures INFO+ logs
_root_logger = logging.getLogger()
if _root_logger.level == logging.NOTSET or _root_logger.level > logging.INFO:
    _root_logger.setLevel(logging.INFO)
if not _root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _log_request(parsed: dict[str, Any]) -> None:
    """Logs every incoming HTTP request with method, path, query, IP, headers, and body."""
    logger.info(
        "[API Request] %s %s | client_ip=%s | query_params=%s | headers=%s | body=%s",
        parsed.get("method"),
        parsed.get("path"),
        parsed.get("client_ip"),
        json.dumps(parsed.get("query_params") or {}),
        json.dumps(parsed.get("headers") or {}),
        parsed.get("body") or "",
    )


def _log_response(method: str, path: str, response: dict[str, Any]) -> None:
    """Logs every outgoing HTTP response with status code, headers, and body/HTML summary."""
    status_code = response.get("statusCode")
    headers = response.get("headers") or {}
    body = str(response.get("body") or "")
    content_type = str(headers.get("Content-Type") or headers.get("content-type") or "")

    if "text/html" in content_type:
        err_match = re.search(r'<div class="error-text">(.*?)</div>', body, re.DOTALL)
        title_match = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
        summary = {
            "html_title": title_match.group(1).strip() if title_match else "",
            "error_text": err_match.group(1).strip() if err_match else None,
            "html_length": len(body),
        }
        body_log = json.dumps(summary)
    else:
        body_log = body

    if status_code and int(status_code) >= 400:
        logger.warning(
            "[API Response] %s %s -> status=%s | headers=%s | body=%s",
            method,
            path,
            status_code,
            json.dumps(headers),
            body_log,
        )
    else:
        logger.info(
            "[API Response] %s %s -> status=%s | headers=%s | body=%s",
            method,
            path,
            status_code,
            json.dumps(headers),
            body_log,
        )


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

    if error_param:
        msg = (
            "Access was denied by the user. Authorization was cancelled."
            if error_param == "access_denied"
            else f"Authorization failed: {error_param}"
        )
        logger.warning("[OAuth Callback] Error parameter received: %s (club_id=%s)", msg, club_id)
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=msg,
        )
        return _make_html_response(400, html, origin)

    if not code:
        msg = "Missing authorization code in callback parameters."
        logger.warning("[OAuth Callback] %s (club_id=%s)", msg, club_id)
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=msg,
        )
        return _make_html_response(400, html, origin)

    try:
        token_data = intervals_oauth.exchange_code_for_token(code)
    except OAuthError as err:
        logger.error("[OAuth Callback] Token exchange failed for club_id=%s: %s", club_id, err)
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=str(err),
        )
        return _make_html_response(400, html, origin)
    except Exception as err:
        logger.exception("[OAuth Callback] Unexpected error during token exchange for club_id=%s: %s", club_id, err)
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

    try:
        db.save_athlete(
            athlete_id=athlete_id,
            athlete_name=athlete_name,
            access_token=access_token,
            club_id=club_id,
        )
        logger.info(
            "[OAuth Callback] Saved athlete_id=%s athlete_name=%s to club_id=%s",
            athlete_id,
            athlete_name,
            club_id,
        )
    except Exception as err:
        logger.exception(
            "[OAuth Callback] Failed saving athlete_id=%s to DynamoDB (table=%s, region=%s): %s",
            athlete_id,
            config.ATHLETES_TABLE_NAME,
            config.AWS_REGION,
            err,
        )
        html = intervals_oauth.render_callback_html(
            success=False,
            club_id=club_id,
            error_msg=f"Database error saving athlete registration: {err}",
        )
        return _make_html_response(500, html, origin)

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
        logger.warning("[Webhook] Unauthorized webhook attempt (secret mismatch or unset)")
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

        raw_activity_id = activity_data.get("id")
        if raw_activity_id is None or str(raw_activity_id).strip() == "":
            continue

        processed_count += 1

        raw_athlete_id = event.get("athlete_id")
        if not raw_athlete_id:
            continue
        athlete_id = str(raw_athlete_id)

        athlete = db.get_athlete(athlete_id)
        if not athlete:
            # Unknown athlete registered elsewhere or deleted, skip gracefully
            logger.info("[Webhook] Skipping activity_id=%s for unregistered athlete_id=%s", raw_activity_id, athlete_id)
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
    parsed["path"] = path

    _log_request(parsed)

    origin = parsed["headers"].get("origin")
    client_ip = parsed["client_ip"]

    try:
        # Rate limiting check
        if rate_limiter.is_rate_limited(client_ip):
            response = _make_response(429, {"error": "Too Many Requests"}, origin)
        # Handle CORS preflight
        elif method == "OPTIONS":
            response = {
                "statusCode": 204,
                "headers": _make_cors_headers(origin),
                "body": "",
            }
        # Route: GET /oauth/callback
        elif method == "GET" and path == "/oauth/callback":
            response = _handle_oauth_callback(parsed["query_params"], origin)
        # Route: POST /webhook
        elif method == "POST" and path == "/webhook":
            response = _handle_webhook(parsed["body"], origin)
        # Route: POST /auth/token
        elif method == "POST" and path == "/auth/token":
            response = _handle_auth_token(parsed["headers"], origin)
        # Route: GET /
        elif method == "GET" and path == "/":
            response = _handle_dashboard(parsed["headers"], parsed["query_params"], origin)
        # 404 Fallback for unhandled routes
        else:
            response = _make_response(404, {"error": "Not Found", "path": path, "method": method}, origin)
    except Exception as err:
        logger.exception("[API Unhandled Error] %s %s: %s", method, path, err)
        response = _make_response(500, {"error": f"Internal Server Error: {err}"}, origin)

    _log_response(method, path, response)
    return response


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

    import os
    port = int(os.environ.get("PORT", "5000"))
    print(f"Starting local development server on http://localhost:{port}...")
    app.run(host="0.0.0.0", port=port, debug=True)

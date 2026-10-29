"""
backend_source.py - AWS Lambda Function URL Router & Local Dev Server.

Routes:
  - GET  /               -> Dashboard data (JSON)
  - POST /auth/token     -> HMAC-SHA256 handshake for frontend Bearer token
  - GET  /oauth/callback -> Intervals.icu OAuth callback & athlete registration (HTML)
  - POST /webhook        -> Ingestion of real-time ACTIVITY_UPLOADED webhooks
"""
import base64
import json
from typing import Any

from api import api_config as config
from api import db
from api import intervals_oauth
from api import rate_limiter
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

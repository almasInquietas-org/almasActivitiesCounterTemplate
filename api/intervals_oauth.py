"""
api/intervals_oauth.py - Configurable OAuth Client & Confirmation Page for Intervals.icu
"""
import html
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from api import api_config as config


class OAuthError(Exception):
    """Exception raised when an OAuth exchange or validation fails."""
    pass


def exchange_code_for_token(code: str) -> dict[str, str]:
    """
    Exchange an authorization code for an athlete access token.

    Calls POST {config.INTERVALS_OAUTH_BASE_URL}/api/oauth/token with:
      - client_id
      - client_secret
      - code

    Returns:
        dict: {"access_token": str, "athlete_id": str, "athlete_name": str}

    Raises:
        OAuthError: If the HTTP request fails, returns non-200, or has missing fields.
    """
    base_url = (config.INTERVALS_OAUTH_BASE_URL or "https://intervals.icu").rstrip("/")
    token_url = f"{base_url}/api/oauth/token"

    payload_data = urllib.parse.urlencode({
        "client_id": config.INTERVALS_CLIENT_ID or "",
        "client_secret": config.INTERVALS_CLIENT_SECRET or "",
        "code": code,
    }).encode("utf-8")

    req = urllib.request.Request(
        url=token_url,
        data=payload_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        err_body = ""
        try:
            err_body = err.read().decode("utf-8")
        except Exception:
            pass
        raise OAuthError(
            f"OAuth token request failed with HTTP status {err.code}: {err.reason}. Response: {err_body}"
        ) from err
    except urllib.error.URLError as err:
        raise OAuthError(f"OAuth network error reaching {token_url}: {err.reason}") from err
    except Exception as err:
        raise OAuthError(f"Unexpected error during OAuth token exchange: {err}") from err

    try:
        data: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as err:
        raise OAuthError(f"Invalid JSON received from OAuth token endpoint: {body}") from err

    if not isinstance(data, dict):
        raise OAuthError(f"Expected JSON object from OAuth endpoint, got {type(data).__name__}")

    access_token = data.get("access_token")
    athlete = data.get("athlete")

    if not access_token:
        raise OAuthError(f"Response missing access_token: {data}")

    if not isinstance(athlete, dict):
        raise OAuthError(f"Response missing or invalid athlete object: {data}")

    athlete_id = athlete.get("id")
    athlete_name = athlete.get("name") or "Athlete"

    if athlete_id is None:
        raise OAuthError(f"Athlete object missing id: {athlete}")

    return {
        "access_token": str(access_token),
        "athlete_id": str(athlete_id),
        "athlete_name": str(athlete_name),
    }


def render_callback_html(
    success: bool,
    athlete_name: str = "",
    club_id: str = "",
    error_msg: str = "",
) -> str:
    """
    Render a responsive, beautifully styled HTML confirmation page matching
    the dashboard teal design system tokens.

    Variables are sanitized with html.escape() to prevent XSS.
    """
    safe_athlete = html.escape(athlete_name or "Athlete")
    safe_club = html.escape(club_id or "default")
    safe_error = html.escape(error_msg or "An unexpected error occurred during authorization.")

    if success:
        status_badge = (
            '<div class="status-badge success">'
            '<svg class="icon" viewBox="0 0 20 20" fill="currentColor">'
            '<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>'
            '</svg>'
            '<span>Connected</span>'
            '</div>'
        )
        headline = "Registration Successful!"
        description = (
            f"Welcome aboard, <strong>{safe_athlete}</strong>!<br>"
            f"Your Intervals.icu account is now linked to club <strong>{safe_club}</strong>. "
            "Your uploaded activities will automatically sync to the dashboard."
        )
        tip_box = (
            '<div class="tip-card">'
            '<div class="tip-title">⚡ How it works</div>'
            '<p class="tip-body">'
            'Upload or sync your rides and runs to Intervals.icu from your GPS device '
            '(Garmin, Wahoo, Polar, Suunto, Coros). Activities are automatically recorded '
            'on the team challenge board.'
            '</p>'
            '</div>'
        )
    else:
        status_badge = (
            '<div class="status-badge error">'
            '<svg class="icon" viewBox="0 0 20 20" fill="currentColor">'
            '<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>'
            '</svg>'
            '<span>Registration Failed</span>'
            '</div>'
        )
        headline = "Could Not Connect"
        description = f'<div class="error-text">{safe_error}</div>'
        tip_box = (
            '<div class="tip-card tip-error">'
            '<div class="tip-title">What should I do?</div>'
            '<p class="tip-body">'
            'Please request a fresh registration link from your club administrator or '
            'try authorizing the application again.'
            '</p>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{"Registration Successful" if success else "Registration Failed"} - Almas Inquietas</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Racing+Sans+One&display=swap" rel="stylesheet">
  <style>
    :root {{
      --activum-teal: #62c0bb;
      --activum-teal-light: #82d0cc;
      --activum-teal-dark: #43aaa4;
      --activum-teal-glow: rgba(98, 192, 187, 0.25);
      --bg-primary: #f0f4f8;
      --bg-card: rgba(255, 255, 255, 0.92);
      --text-primary: #0f172a;
      --text-secondary: #475569;
      --text-muted: #94a3b8;
      --font-body: 'Inter', system-ui, -apple-system, sans-serif;
      --font-display: 'Racing Sans One', system-ui, sans-serif;
    }}

    * {{
      box-init: border-box;
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font-body);
      background-color: var(--bg-primary);
      background-image:
        radial-gradient(ellipse 60% 40% at 50% 0%, rgba(98, 192, 187, 0.18) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 85% 90%, rgba(67, 170, 164, 0.12) 0%, transparent 60%);
      color: var(--text-primary);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}

    .container {{
      width: 100%;
      max-width: 520px;
    }}

    .card {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(148, 163, 184, 0.25);
      border-radius: 24px;
      box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08), 0 4px 12px rgba(98, 192, 187, 0.15);
      padding: 40px 32px;
      text-align: center;
    }}

    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 18px;
      border-radius: 100px;
      font-size: 0.85rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 24px;
    }}

    .status-badge.success {{
      background: linear-gradient(135deg, var(--activum-teal-dark), var(--activum-teal));
      color: #ffffff;
      box-shadow: 0 4px 14px var(--activum-teal-glow);
    }}

    .status-badge.error {{
      background: #ef4444;
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(239, 68, 68, 0.25);
    }}

    .icon {{
      width: 18px;
      height: 18px;
    }}

    h1 {{
      font-family: var(--font-display);
      font-size: 2.2rem;
      line-height: 1.15;
      color: var(--text-primary);
      margin-bottom: 16px;
      letter-spacing: 0.01em;
    }}

    .description {{
      font-size: 1.05rem;
      line-height: 1.6;
      color: var(--text-secondary);
      margin-bottom: 28px;
    }}

    .description strong {{
      color: var(--text-primary);
    }}

    .error-text {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
      padding: 14px 18px;
      border-radius: 12px;
      font-size: 0.95rem;
    }}

    .tip-card {{
      background: rgba(240, 244, 248, 0.7);
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: 16px;
      padding: 20px;
      text-align: left;
      margin-top: 12px;
    }}

    .tip-card.tip-error {{
      background: #fffaf0;
      border-color: #feebc8;
    }}

    .tip-title {{
      font-size: 0.82rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-secondary);
      margin-bottom: 8px;
    }}

    .tip-body {{
      font-size: 0.9rem;
      line-height: 1.5;
      color: var(--text-secondary);
    }}

    .footer {{
      margin-top: 24px;
      font-size: 0.8rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      {status_badge}
      <h1>{headline}</h1>
      <div class="description">{description}</div>
      {tip_box}
      <div class="footer">Almas Inquietas &bull; Intervals.icu Activities Counter</div>
    </div>
  </div>
</body>
</html>"""

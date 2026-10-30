"""
scripts/simulate_webhook.py - CLI tool to simulate real-time Intervals.icu webhooks.

Usage:
    python scripts/simulate_webhook.py --url http://127.0.0.1:5000 --secret dev-webhook-secret
    python scripts/simulate_webhook.py --url https://<lambda-url> --secret pre-secret --athlete-id i_demo_01 --km 15.4 --type Run
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def send_webhook(
    url: str,
    secret: str,
    athlete_id: str = "i_demo_01",
    activity_title: str = "Entreno en directo (Demo)",
    act_type: str = "Run",
    km: float = 12.5,
) -> tuple[int, dict]:
    """
    Constructs and sends an ACTIVITY_UPLOADED webhook payload to target API URL.
    Returns (status_code, response_dict).
    """
    base_url = url.rstrip("/")
    webhook_endpoint = f"{base_url}/webhook"

    activity_id = int(time.time())
    distance_meters = int(round(km * 1000.0))
    moving_time_seconds = int(km * 300)  # ~5 min/km estimate

    payload = {
        "secret": secret,
        "events": [
            {
                "athlete_id": athlete_id,
                "type": "ACTIVITY_UPLOADED",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "activity": {
                    "id": activity_id,
                    "name": activity_title,
                    "type": act_type,
                    "sport_type": act_type,
                    "distance": distance_meters,
                    "moving_time": moving_time_seconds,
                    "total_elevation_gain": 120,
                    "start_date_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                },
            }
        ],
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=webhook_endpoint,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body_raw = response.read().decode("utf-8")
            try:
                body_json = json.loads(body_raw)
            except Exception:
                body_json = {"raw": body_raw}
            return status, body_json
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8") if err.fp else ""
        try:
            body_json = json.loads(err_body)
        except Exception:
            body_json = {"error": err_body or err.reason}
        return err.code, body_json
    except urllib.error.URLError as err:
        return 0, {"error": str(err.reason)}


def main():
    parser = argparse.ArgumentParser(description="Simulate real-time Intervals.icu ACTIVITY_UPLOADED webhook")
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="Target API Base URL")
    parser.add_argument("--secret", default="dev-webhook-secret", help="Intervals.icu webhook secret")
    parser.add_argument("--athlete-id", default="i_demo_01", help="Target registered athlete ID")
    parser.add_argument("--name", default="Entreno en directo (Demo)", help="Activity Title")
    parser.add_argument("--type", default="Run", choices=["Run", "Ride", "Swim", "Hike", "Walk"], help="Sport type")
    parser.add_argument("--km", type=float, default=12.5, help="Activity distance in kilometers")

    args = parser.parse_args()

    print(f"🚀 Sending demo webhook to {args.url}/webhook...")
    print(f"   Athlete: {args.athlete_id} | Activity: '{args.name}' ({args.type}) | Distance: {args.km} km")

    status, response = send_webhook(
        url=args.url,
        secret=args.secret,
        athlete_id=args.athlete_id,
        activity_title=args.name,
        act_type=args.type,
        km=args.km,
    )

    print(f"\n📡 Response Status: {status}")
    print(f"   Body: {json.dumps(response, indent=2)}")

    if status == 200 and response.get("status") == "ok":
        print("✅ Activity processed and saved successfully! Check the dashboard.")
    else:
        print("❌ Webhook simulation failed or was rejected.")
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
db.py - DynamoDB Data Access Layer for ATHLETES and ACTIVITIES tables.
"""
from datetime import datetime, timezone
import boto3
from api import api_config as config


def get_dynamodb_resource():
    """Returns a boto3 DynamoDB resource configured with current config region."""
    return boto3.resource("dynamodb", region_name=config.AWS_REGION)


def get_athletes_table():
    """Returns the DynamoDB Table resource for the ATHLETES table."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(config.ATHLETES_TABLE_NAME)


def get_athlete(athlete_id: str) -> dict | None:
    """
    Lookup athlete by athlete_id (PK) in ATHLETES table.
    Returns the athlete dict or None if not found.
    """
    table = get_athletes_table()
    response = table.get_item(Key={"athlete_id": str(athlete_id)})
    return response.get("Item")


def save_athlete(
    athlete_id: str,
    athlete_name: str,
    access_token: str,
    club_id: str,
) -> dict:
    """
    Creates or updates the athlete item in ATHLETES_TABLE_NAME.
    Deduplicates club_id into the clubs list and updates access_token/updated_at.
    Returns the stored item dictionary.
    """
    table = get_athletes_table()
    existing = get_athlete(athlete_id)

    if existing and isinstance(existing.get("clubs"), list):
        clubs = list(existing["clubs"])
    else:
        clubs = []

    clean_club = (club_id or "").strip()
    if clean_club and clean_club not in clubs:
        clubs.append(clean_club)

    now_iso = datetime.now(timezone.utc).isoformat()

    item = {
        "athlete_id": str(athlete_id),
        "athlete_name": str(athlete_name),
        "access_token": str(access_token),
        "clubs": clubs,
        "updated_at": now_iso,
    }

    table.put_item(Item=item)
    return item

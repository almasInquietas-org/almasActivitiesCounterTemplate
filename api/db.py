"""
db.py - DynamoDB Data Access Layer for ATHLETES and ACTIVITIES tables.
"""
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
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


def get_activities_table():
    """Returns the DynamoDB Table resource for the ACTIVITIES table."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(config.ACTIVITIES_TABLE_NAME)


def save_activity(
    activity: dict,
    athlete_id: str,
    athlete_name: str,
    clubs: list[str],
) -> bool:
    """
    Saves an activity in ACTIVITIES_TABLE_NAME idempotently.
    Uses ConditionExpression='attribute_not_exists(activity_id)'.
    Returns True if newly inserted, False if already exists.
    """
    table = get_activities_table()
    activity_id = str(activity.get("id"))

    # Convert distance to km (Intervals.icu reports meters in 'distance')
    if "distance_km" in activity:
        dist_km = Decimal(str(round(float(activity["distance_km"]), 2)))
    elif "distance" in activity and activity["distance"] is not None:
        dist_meters = float(activity["distance"])
        dist_km = Decimal(str(round(dist_meters / 1000.0, 2)))
    else:
        dist_km = Decimal("0.00")

    elevation = activity.get("total_elevation_gain")
    if elevation is not None:
        elevation_gain = Decimal(str(round(float(elevation), 2)))
    else:
        elevation_gain = Decimal("0")

    moving_time = activity.get("moving_time_seconds")
    if moving_time is None:
        moving_time = activity.get("moving_time", 0)
    moving_time_int = int(moving_time or 0)

    start_date = (
        activity.get("start_date_local")
        or activity.get("start_date")
        or ""
    )

    title = activity.get("title") or activity.get("name") or ""
    act_type = activity.get("type") or ""
    sport_type = activity.get("sport_type") or act_type

    item = {
        "activity_id": activity_id,
        "athlete_id": str(athlete_id),
        "athlete": str(athlete_name),
        "clubs": list(clubs) if clubs else [],
        "title": str(title),
        "type": str(act_type),
        "sport_type": str(sport_type),
        "distance_km": dist_km,
        "moving_time_seconds": moving_time_int,
        "total_elevation_gain": elevation_gain,
        "start_date": str(start_date),
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(activity_id)",
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def get_all_activities() -> list[dict]:
    """
    Performs a full paginated scan of ACTIVITIES_TABLE_NAME and returns all items.
    """
    table = get_activities_table()
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


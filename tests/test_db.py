import pytest
from moto import mock_aws
from api import db, api_config


def test_get_athlete_not_found(dynamodb_mock):
    athlete = db.get_athlete("non_existent_id")
    assert athlete is None


def test_save_and_get_athlete(dynamodb_mock):
    athlete_data = db.save_athlete(
        athlete_id="i12345",
        athlete_name="Daniel Fernandez",
        access_token="token_abc_123",
        club_id="almas_inquietas",
    )

    assert athlete_data["athlete_id"] == "i12345"
    assert athlete_data["athlete_name"] == "Daniel Fernandez"
    assert athlete_data["access_token"] == "token_abc_123"
    assert athlete_data["clubs"] == ["almas_inquietas"]
    assert "updated_at" in athlete_data

    # Retrieve from DB and verify
    fetched = db.get_athlete("i12345")
    assert fetched is not None
    assert fetched["athlete_id"] == "i12345"
    assert fetched["athlete_name"] == "Daniel Fernandez"
    assert fetched["access_token"] == "token_abc_123"
    assert fetched["clubs"] == ["almas_inquietas"]
    assert fetched["updated_at"] == athlete_data["updated_at"]


def test_save_athlete_multi_club_no_duplicates(dynamodb_mock):
    # Register first club
    db.save_athlete(
        athlete_id="i12345",
        athlete_name="Daniel Fernandez",
        access_token="token_1",
        club_id="club_a",
    )

    # Register same club again - should not duplicate
    updated_1 = db.save_athlete(
        athlete_id="i12345",
        athlete_name="Daniel Fernandez",
        access_token="token_1_new",
        club_id="club_a",
    )
    assert updated_1["clubs"] == ["club_a"]
    assert updated_1["access_token"] == "token_1_new"

    # Register a second club
    updated_2 = db.save_athlete(
        athlete_id="i12345",
        athlete_name="Daniel Fernandez Updated",
        access_token="token_2",
        club_id="club_b",
    )
    assert "club_a" in updated_2["clubs"]
    assert "club_b" in updated_2["clubs"]
    assert len(updated_2["clubs"]) == 2
    assert updated_2["athlete_name"] == "Daniel Fernandez Updated"
    assert updated_2["access_token"] == "token_2"

    # Verify via get_athlete
    fetched = db.get_athlete("i12345")
    assert fetched["clubs"] == updated_2["clubs"]
    assert fetched["athlete_name"] == "Daniel Fernandez Updated"
    assert fetched["access_token"] == "token_2"


def test_save_athlete_empty_club_id(dynamodb_mock):
    # When club_id is empty or None
    result = db.save_athlete(
        athlete_id="i99999",
        athlete_name="Solo Athlete",
        access_token="tok",
        club_id="",
    )
    assert result["clubs"] == []


def test_save_activity_new(dynamodb_mock):
    from decimal import Decimal

    activity_data = {
        "id": "act_1001",
        "name": "Morning Run",
        "type": "Run",
        "sport_type": "Run",
        "distance": 10050.0,  # 10.05 km in meters
        "moving_time": 3600,
        "total_elevation_gain": 120.5,
        "start_date_local": "2026-10-24T08:00:00",
    }

    saved = db.save_activity(
        activity=activity_data,
        athlete_id="ath_1",
        athlete_name="Daniel Fernandez",
        clubs=["almas_inquietas"],
    )
    assert saved is True

    # Retrieve directly from DynamoDB
    table = db.get_activities_table()
    res = table.get_item(Key={"activity_id": "act_1001"})
    item = res.get("Item")
    assert item is not None
    assert item["activity_id"] == "act_1001"
    assert item["athlete_id"] == "ath_1"
    assert item["athlete"] == "Daniel Fernandez"
    assert item["clubs"] == ["almas_inquietas"]
    assert item["title"] == "Morning Run"
    assert item["type"] == "Run"
    assert item["sport_type"] == "Run"
    assert item["distance_km"] == Decimal("10.05")
    assert item["moving_time_seconds"] == 3600
    assert item["total_elevation_gain"] == Decimal("120.5")
    assert item["start_date"] == "2026-10-24T08:00:00"


def test_save_activity_idempotency_duplicate(dynamodb_mock):
    activity_data = {
        "id": 48566307,  # integer id converted to str
        "name": "Evening Ride",
        "type": "Ride",
        "distance": 25000,
        "start_date_local": "2026-10-24T18:00:00",
    }
    first_save = db.save_activity(
        activity=activity_data,
        athlete_id="ath_2",
        athlete_name="Maria Lopez",
        clubs=["almas_inquietas"],
    )
    assert first_save is True

    # Second save should detect attribute_not_exists condition failure and return False
    second_save = db.save_activity(
        activity=activity_data,
        athlete_id="ath_2",
        athlete_name="Maria Lopez",
        clubs=["almas_inquietas"],
    )
    assert second_save is False


def test_save_activity_fallback_fields(dynamodb_mock):
    from decimal import Decimal

    activity_data = {
        "id": "act_minimal",
        "distance_km": 5.25,  # already in km
        "start_date": "2026-10-23T10:00:00",
    }
    saved = db.save_activity(
        activity=activity_data,
        athlete_id="ath_3",
        athlete_name="Alex Runner",
        clubs=[],
    )
    assert saved is True
    table = db.get_activities_table()
    item = table.get_item(Key={"activity_id": "act_minimal"}).get("Item")
    assert item["distance_km"] == Decimal("5.25")
    assert item["start_date"] == "2026-10-23T10:00:00"
    assert item["title"] == ""
    assert item["type"] == ""
    assert item["sport_type"] == ""
    assert item["moving_time_seconds"] == 0
    assert item["total_elevation_gain"] == Decimal("0")


def test_get_all_activities(dynamodb_mock):
    assert db.get_all_activities() == []

    # Insert 2 activities
    db.save_activity(
        activity={"id": "1", "distance": 5000, "start_date_local": "2026-10-20T00:00:00"},
        athlete_id="ath_1",
        athlete_name="Ath 1",
        clubs=["club_a"],
    )
    db.save_activity(
        activity={"id": "2", "distance": 10000, "start_date_local": "2026-10-21T00:00:00"},
        athlete_id="ath_2",
        athlete_name="Ath 2",
        clubs=["club_b"],
    )

    activities = db.get_all_activities()
    assert len(activities) == 2
    ids = {a["activity_id"] for a in activities}
    assert ids == {"1", "2"}

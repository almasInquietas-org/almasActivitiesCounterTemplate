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

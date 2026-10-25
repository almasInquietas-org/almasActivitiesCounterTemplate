import pytest
from decimal import Decimal
from api import services, api_config


def test_build_dashboard_data_empty(monkeypatch):
    monkeypatch.setattr("api.services.get_all_activities", lambda: [])
    monkeypatch.setattr("api.services.config.GOAL_KM", 1000.0)
    monkeypatch.setattr("api.services.config.TITLE", "Test Club")
    monkeypatch.setattr("api.services.config.CHECKPOINTS", [250.0, 500.0, 750.0])

    data = services.build_dashboard_data()
    assert data["total_km"] == 0.0
    assert data["total_activities"] == 0
    assert data["top_athletes"] == []
    assert data["last_activities"] == []
    assert data["config"]["goal_km"] == 1000.0
    assert data["config"]["title"] == "Test Club"
    assert data["config"]["checkpoints"] == [250.0, 500.0, 750.0]


def test_build_dashboard_data_goal_km_none(monkeypatch):
    monkeypatch.setattr("api.services.get_all_activities", lambda: [])
    monkeypatch.setattr("api.services.config.GOAL_KM", None)
    monkeypatch.setattr("api.services.config.CHECKPOINTS", [250.0, 500.0])

    data = services.build_dashboard_data()
    assert data["config"]["goal_km"] is None
    # Section 6 contract: checkpoints empty list if goal_km is null
    assert data["config"]["checkpoints"] == []


def test_build_dashboard_data_collision_free_ranking(monkeypatch):
    """
    Two athletes with the same name 'Alex Smith' but different athlete_id.
    They must be ranked independently!
    """
    raw_activities = [
        {
            "activity_id": "act_1",
            "athlete_id": "id_101",
            "athlete": "Alex Smith",
            "clubs": ["almas_inquietas"],
            "title": "Run 1",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("15.50"),
            "moving_time_seconds": 3600,
            "total_elevation_gain": Decimal("100"),
            "start_date": "2026-10-20T10:00:00",
        },
        {
            "activity_id": "act_2",
            "athlete_id": "id_101",
            "athlete": "Alex Smith",
            "clubs": ["almas_inquietas"],
            "title": "Run 2",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("10.00"),
            "moving_time_seconds": 2400,
            "total_elevation_gain": Decimal("50"),
            "start_date": "2026-10-22T10:00:00",
        },
        {
            "activity_id": "act_3",
            "athlete_id": "id_102",  # Different person with same display name
            "athlete": "Alex Smith",
            "clubs": ["almas_inquietas"],
            "title": "Alex 2 Run",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("20.00"),
            "moving_time_seconds": 4500,
            "total_elevation_gain": Decimal("120"),
            "start_date": "2026-10-21T10:00:00",
        },
    ]

    monkeypatch.setattr("api.services.get_all_activities", lambda: raw_activities)

    data = services.build_dashboard_data()
    assert data["total_km"] == 45.5
    assert data["total_activities"] == 3
    assert len(data["top_athletes"]) == 2

    # id_101 has 15.5 + 10.0 = 25.5 km, lastIncrement = 10.0 (from 2026-10-22)
    # id_102 has 20.0 km, lastIncrement = 20.0
    first = data["top_athletes"][0]
    second = data["top_athletes"][1]

    assert first["athlete_name"] == "Alex Smith"
    assert first["currentKm"] == 25.5
    assert first["lastIncrement"] == 10.0

    assert second["athlete_name"] == "Alex Smith"
    assert second["currentKm"] == 20.0
    assert second["lastIncrement"] == 20.0


def test_build_dashboard_data_club_filter(monkeypatch):
    raw_activities = [
        {
            "activity_id": "act_1",
            "athlete_id": "id_1",
            "athlete": "Ath 1",
            "clubs": ["club_a"],
            "title": "Run A",
            "type": "Run",
            "distance_km": Decimal("10.00"),
            "start_date": "2026-10-20T10:00:00",
        },
        {
            "activity_id": "act_2",
            "athlete_id": "id_2",
            "athlete": "Ath 2",
            "clubs": ["club_b"],
            "title": "Run B",
            "type": "Run",
            "distance_km": Decimal("15.00"),
            "start_date": "2026-10-21T10:00:00",
        },
    ]
    monkeypatch.setattr("api.services.get_all_activities", lambda: raw_activities)

    data_a = services.build_dashboard_data(club_filter="club_a")
    assert data_a["total_km"] == 10.0
    assert data_a["total_activities"] == 1
    assert len(data_a["top_athletes"]) == 1
    assert data_a["top_athletes"][0]["athlete_name"] == "Ath 1"

    data_b = services.build_dashboard_data(club_filter="club_b")
    assert data_b["total_km"] == 15.0
    assert data_b["total_activities"] == 1


def test_build_dashboard_data_filters_and_last_activities(monkeypatch):
    raw_activities = [
        {
            "activity_id": "act_1",
            "athlete_id": "id_1",
            "athlete": "Runner 1",
            "title": "Morning [skip] Run",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("5.0"),
            "start_date": "2026-10-20T10:00:00",
        },
        {
            "activity_id": "act_2",
            "athlete_id": "id_1",
            "athlete": "Runner 1",
            "title": "Morning Swim",
            "type": "Swim",
            "sport_type": "Swim",
            "distance_km": Decimal("2.0"),
            "start_date": "2026-10-21T10:00:00",
        },
        {
            "activity_id": "act_3",
            "athlete_id": "id_1",
            "athlete": "Runner 1",
            "title": "Valid Run Old",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("10.0"),
            "start_date": "2026-10-15T10:00:00",  # before START_DATE
        },
        {
            "activity_id": "act_4",
            "athlete_id": "id_1",
            "athlete": "Runner 1",
            "title": "Valid Run New",
            "type": "Run",
            "sport_type": "Run",
            "distance_km": Decimal("12.0"),
            "moving_time_seconds": 3600,
            "start_date": "2026-10-22T10:00:00",
        },
    ]
    monkeypatch.setattr("api.services.get_all_activities", lambda: raw_activities)
    monkeypatch.setattr("api.services.config.ACT_TYPE_FILTER", "Run")
    monkeypatch.setattr("api.services.config.ACT_TITLE_FILTER", "[skip]")
    monkeypatch.setattr("api.services.config.START_DATE", "2026-10-18")
    monkeypatch.setattr("api.services.config.LAST_ACT", 5)

    data = services.build_dashboard_data()
    assert data["total_km"] == 12.0
    assert data["total_activities"] == 1
    assert len(data["last_activities"]) == 1
    assert data["last_activities"][0]["id"] == "act_4"
    assert data["last_activities"][0]["date"] == "2026-10-22T10:00:00"
    assert data["last_activities"][0]["distance_km"] == 12.0

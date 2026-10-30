"""
services.py - Business logic and dashboard data aggregation.
"""
from decimal import Decimal
from api import api_config as config
from api.db import get_all_activities


def _matches_filters(
    activity: dict,
    club_filter: str | None = None,
) -> bool:
    """
    Evaluates whether an activity satisfies club, sport type, title, and start date filters.
    """
    # 1. Club filter: parameter takes precedence over config.CLUB_FILTER
    target_club = (club_filter if club_filter is not None else config.CLUB_FILTER) or ""
    target_club = target_club.strip()
    if target_club:
        clubs = activity.get("clubs") or []
        if target_club not in clubs:
            return False

    # 2. Activity type / sport_type filter (supports comma-separated list of types)
    act_type_filter = (config.ACT_TYPE_FILTER or "").strip().lower()
    if act_type_filter:
        allowed_types = {t.strip() for t in act_type_filter.split(",") if t.strip()}
        act_type = str(activity.get("type") or "").strip().lower()
        sport_type = str(activity.get("sport_type") or "").strip().lower()
        if act_type not in allowed_types and sport_type not in allowed_types:
            return False

    # 3. Title filter (substring exclusion, case-insensitive)
    title_filter = (config.ACT_TITLE_FILTER or "").strip().lower()
    if title_filter:
        title = str(activity.get("title") or "").lower()
        if title_filter in title:
            return False

    # 4. Start date filter (string ISO prefix comparison, e.g. '2026-10-01' <= '2026-10-24T06:30:00')
    start_date_filter = (config.START_DATE or "").strip()
    if start_date_filter:
        act_date = str(activity.get("start_date") or "")
        if act_date and act_date < start_date_filter:
            return False

    return True


def build_dashboard_data(club_filter: str | None = None) -> dict:
    """
    Aggregates activities from ACTIVITIES table into the dashboard data structure:
    - total_km
    - total_activities
    - top_athletes (grouped by athlete_id, collision-free)
    - last_activities (sorted by date descending, max config.LAST_ACT)
    - config (goal_km, title, checkpoints)
    """
    all_activities = get_all_activities()

    filtered_activities = [
        act for act in all_activities
        if _matches_filters(act, club_filter=club_filter)
    ]

    total_km = 0.0
    athletes_stats: dict[str, dict] = {}
    normalized_activities: list[dict] = []

    for act in filtered_activities:
        # Distance
        raw_dist = act.get("distance_km", 0.0)
        dist_km = float(raw_dist) if isinstance(raw_dist, (Decimal, int, float)) else 0.0
        dist_km = round(dist_km, 2)
        total_km += dist_km

        # Athlete identification: primary key is athlete_id
        athlete_id = str(act.get("athlete_id") or act.get("athlete") or "unknown")
        athlete_name = str(act.get("athlete") or "Unknown")
        start_date = str(act.get("start_date") or "")

        if athlete_id not in athletes_stats:
            athletes_stats[athlete_id] = {
                "athlete_name": athlete_name,
                "currentKm": 0.0,
                "activities": [],
            }
        athletes_stats[athlete_id]["currentKm"] += dist_km
        athletes_stats[athlete_id]["activities"].append({
            "distance_km": dist_km,
            "start_date": start_date,
        })

        # Activity item representation
        moving_time = act.get("moving_time_seconds")
        if moving_time is None:
            moving_time = act.get("moving_time", 0)

        normalized_activities.append({
            "id": str(act.get("activity_id") or act.get("id") or ""),
            "title": str(act.get("title") or ""),
            "athlete": athlete_name,
            "type": str(act.get("type") or ""),
            "sport_type": str(act.get("sport_type") or act.get("type") or ""),
            "distance_km": dist_km,
            "moving_time_seconds": int(moving_time or 0),
            "date": start_date,
        })

    total_km = round(total_km, 2)

    # Compute top_athletes
    top_athletes = []
    for ath_id, stat in athletes_stats.items():
        # Find the activity with highest start_date to determine lastIncrement
        sorted_user_acts = sorted(
            stat["activities"],
            key=lambda a: a["start_date"],
            reverse=True,
        )
        last_increment = sorted_user_acts[0]["distance_km"] if sorted_user_acts else 0.0

        top_athletes.append({
            "athlete_id": ath_id,
            "athlete_name": stat["athlete_name"],
            "currentKm": round(stat["currentKm"], 2),
            "lastIncrement": round(last_increment, 2),
        })

    # Sort top_athletes descending by currentKm
    top_athletes.sort(key=lambda a: a["currentKm"], reverse=True)
    top_athletes = top_athletes[:10]

    # Sort last_activities descending by date
    normalized_activities.sort(key=lambda a: a["date"], reverse=True)
    limit = config.LAST_ACT if (config.LAST_ACT and config.LAST_ACT > 0) else 10
    last_activities = normalized_activities[:limit]

    # Config section
    goal_km = config.GOAL_KM
    if goal_km is not None:
        checkpoints = sorted(config.CHECKPOINTS or [])
    else:
        checkpoints = []

    return {
        "total_km": total_km,
        "total_activities": len(filtered_activities),
        "top_athletes": top_athletes,
        "last_activities": last_activities,
        "config": {
            "goal_km": goal_km,
            "title": config.TITLE or "Almas Inquietas Activities",
            "checkpoints": checkpoints,
        },
    }

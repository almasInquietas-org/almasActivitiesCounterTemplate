"""
scripts/seed_demo_data.py - Populates DynamoDB with realistic demo data for PRE and DEV.

Usage:
    python scripts/seed_demo_data.py --env dev --reset
    python scripts/seed_demo_data.py --env pre --reset --club almas_inquietas
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import boto3

# Demo Athletes (Spanish names representing a vibrant endurance club)
DEMO_ATHLETES = [
    {"id": "i_demo_01", "name": "Daniel Fernández", "token": "tok_demo_01"},
    {"id": "i_demo_02", "name": "Lucía Martínez", "token": "tok_demo_02"},
    {"id": "i_demo_03", "name": "Carlos Navarro", "token": "tok_demo_03"},
    {"id": "i_demo_04", "name": "Elena Gómez", "token": "tok_demo_04"},
    {"id": "i_demo_05", "name": "Marcos Serrano", "token": "tok_demo_05"},
    {"id": "i_demo_06", "name": "Sofía Morales", "token": "tok_demo_06"},
    {"id": "i_demo_07", "name": "Javier Vidal", "token": "tok_demo_07"},
    {"id": "i_demo_08", "name": "Paula Romero", "token": "tok_demo_08"},
    {"id": "i_demo_09", "name": "David Alarcón", "token": "tok_demo_09"},
    {"id": "i_demo_10", "name": "Andrea Castillo", "token": "tok_demo_10"},
    {"id": "i_demo_11", "name": "Roberto Molina", "token": "tok_demo_11"},
    {"id": "i_demo_12", "name": "Marta Benítez", "token": "tok_demo_12"},
]

# Curated activities template across the last 14 days
# Distribution: Runs (tempo, long, intervals), Rides (gran fondo, morning spin), Swims, Hikes
ACTIVITY_TEMPLATES = [
    # Daniel Fernández
    ("i_demo_01", "Tirada larga de domingo por Collserola", "Run", 21.2, 7200, 380, 1),
    ("i_demo_01", "Series 6x1000m pista", "Run", 11.5, 3300, 25, 3),
    ("i_demo_01", "Salida ciclista carretera El Garraf", "Ride", 75.4, 9800, 850, 5),
    ("i_demo_01", "Rodaje regenerativo matutino", "Run", 8.2, 2700, 60, 7),
    ("i_demo_01", "Subida ciclista a Montserrat", "Ride", 82.0, 11200, 1200, 10),

    # Lucía Martínez
    ("i_demo_02", "Gravel bike por pistas del Penedès", "Ride", 68.5, 9200, 620, 2),
    ("i_demo_02", "Entreno de natación técnica 2500m", "Swim", 2.5, 2800, 0, 3),
    ("i_demo_02", "Rodaje continuo a ritmo maratón", "Run", 16.0, 4800, 110, 6),
    ("i_demo_02", "Salida grupal sábado carretera", "Ride", 94.2, 12400, 950, 8),
    ("i_demo_02", "Trail running subida La Mola", "Run", 14.8, 5400, 710, 11),

    # Carlos Navarro
    ("i_demo_03", "Gran Fondo puertos de montaña", "Ride", 112.5, 14600, 1650, 1),
    ("i_demo_03", "Rodaje suave recuperación", "Ride", 35.0, 4500, 150, 4),
    ("i_demo_03", "Contrarreloj llana de prueba", "Ride", 42.0, 4200, 180, 7),
    ("i_demo_03", "Gravel tarde otoñal", "Ride", 55.4, 7600, 490, 12),

    # Elena Gómez
    ("i_demo_04", "Media Maratón preparatoria", "Run", 21.1, 5900, 130, 2),
    ("i_demo_04", "Fartlek cambios de ritmo", "Run", 12.4, 3500, 90, 5),
    ("i_demo_04", "Natación aguas abiertas", "Swim", 3.0, 3200, 0, 7),
    ("i_demo_04", "Rodaje suave en ayunas", "Run", 10.0, 3100, 75, 9),

    # Marcos Serrano
    ("i_demo_05", "Ruta BTT trialeras y senderos", "Ride", 44.0, 7800, 890, 2),
    ("i_demo_05", "Senderismo activo con desnivel", "Hike", 15.5, 9600, 650, 6),
    ("i_demo_05", "Salida carretera ritmo alegre", "Ride", 62.0, 8100, 540, 8),
    ("i_demo_05", "BTT nocturna entre semana", "Ride", 31.5, 5200, 410, 13),

    # Sofía Morales
    ("i_demo_06", "Tirada larga 28km fondo", "Run", 28.0, 8800, 220, 3),
    ("i_demo_06", "Entreno de cuestas explosivas", "Run", 9.5, 3200, 290, 6),
    ("i_demo_06", "Rodaje ritmo vivo progresivo", "Run", 15.2, 4400, 120, 10),
    ("i_demo_06", "Series cortas 10x400m", "Run", 8.8, 2600, 30, 12),

    # Javier Vidal
    ("i_demo_07", "Circuito carretera Costa Brava", "Ride", 88.0, 11500, 920, 1),
    ("i_demo_07", "Sesión de series en subida", "Ride", 48.0, 6600, 780, 5),
    ("i_demo_07", "Paseo activo y caminata", "Walk", 6.5, 4200, 50, 9),

    # Paula Romero
    ("i_demo_08", "Entrenamiento natación series 100m", "Swim", 2.2, 2500, 0, 2),
    ("i_demo_08", "Rodaje cómodo matinal", "Run", 11.0, 3600, 80, 4),
    ("i_demo_08", "Travesía natación fin de semana", "Swim", 3.8, 4100, 0, 7),
    ("i_demo_08", "Carrera continua ritmo fácil", "Run", 13.5, 4300, 95, 11),

    # David Alarcón
    ("i_demo_09", "Ultra Trail tramo técnico", "Run", 32.4, 14200, 1450, 3),
    ("i_demo_09", "Caminata de altura Pirineos", "Hike", 18.0, 13800, 980, 8),
    ("i_demo_09", "Carrera regenerativa", "Run", 7.5, 2600, 40, 12),

    # Andrea Castillo
    ("i_demo_10", "Salida cicloturista tranquila", "Ride", 52.0, 7200, 410, 4),
    ("i_demo_10", "Rodaje por el paseo marítimo", "Run", 10.2, 3300, 15, 6),
    ("i_demo_10", "Gravel descubriendo caminos", "Ride", 41.5, 6100, 320, 10),

    # Roberto Molina
    ("i_demo_11", "Tirada media con cambios", "Run", 17.5, 5200, 140, 5),
    ("i_demo_11", "Rodaje suave en parque", "Run", 8.0, 2550, 30, 9),
    ("i_demo_11", "Salida BTT dominguera", "Ride", 38.0, 6400, 510, 13),

    # Marta Benítez
    ("i_demo_12", "Ciclismo carretera llano", "Ride", 65.0, 8400, 280, 3),
    ("i_demo_12", "Series 5x2000m ritmo 10k", "Run", 14.0, 4100, 60, 7),
    ("i_demo_12", "Sesión de piscina recuperación", "Swim", 1.8, 2100, 0, 11),
]

ATHLETES_TABLE_NAME = ""
ACTIVITIES_TABLE_NAME = ""


def get_tables(env: str):
    """Resolve DynamoDB Table resources based on environment."""
    global ATHLETES_TABLE_NAME, ACTIVITIES_TABLE_NAME

    target_env = env.strip().lower()
    if target_env == "prod" or target_env.endswith("_prod"):
        print("❌ CRITICAL SAFETY ERROR: Refusing to seed or reset PRODUCTION tables!", file=sys.stderr)
        sys.exit(1)

    if target_env == "pre":
        athletes_env = os.environ.get("ATHLETES_TABLE_NAME")
        activities_env = os.environ.get("ACTIVITIES_TABLE_NAME")
        ATHLETES_TABLE_NAME = athletes_env if athletes_env else "ATHLETES_PRE"
        ACTIVITIES_TABLE_NAME = activities_env if activities_env else "ACTIVITIES_PRE"
    else:
        athletes_env = os.environ.get("ATHLETES_TABLE_NAME")
        activities_env = os.environ.get("ACTIVITIES_TABLE_NAME")
        ATHLETES_TABLE_NAME = athletes_env if athletes_env else "ATHLETES_DEV"
        ACTIVITIES_TABLE_NAME = activities_env if activities_env else "ACTIVITIES_DEV"

    # CRITICAL SAFETY CHECK: Refuse to touch any table ending with _PROD
    if ATHLETES_TABLE_NAME.upper().endswith("_PROD") or ACTIVITIES_TABLE_NAME.upper().endswith("_PROD"):
        print("❌ CRITICAL SAFETY ERROR: Refusing to seed or reset PRODUCTION tables!", file=sys.stderr)
        sys.exit(1)

    region = os.environ.get("AWS_REGION", "eu-west-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(ATHLETES_TABLE_NAME), dynamodb.Table(ACTIVITIES_TABLE_NAME)


def truncate_table(table, key_name: str):
    """Scans and deletes all items from a table."""
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan.get("Items", []):
            batch.delete_item(Key={key_name: item[key_name]})

    while "LastEvaluatedKey" in scan:
        scan = table.scan(ExclusiveStartKey=scan["LastEvaluatedKey"])
        with table.batch_writer() as batch:
            for item in scan.get("Items", []):
                batch.delete_item(Key={key_name: item[key_name]})


def seed(env: str = "dev", reset: bool = False, club: str = "almas_inquietas") -> dict:
    """
    Seeds athletes and activities into target environment.
    Returns summary stats dict.
    """
    athletes_table, activities_table = get_tables(env)

    if reset:
        print(f"🧹 Resetting tables for {env.upper()}...")
        truncate_table(athletes_table, "athlete_id")
        truncate_table(activities_table, "activity_id")
        print("   Tables wiped successfully.")

    athlete_map = {a["id"]: a["name"] for a in DEMO_ATHLETES}

    # Seed athletes
    print(f"👥 Seeding {len(DEMO_ATHLETES)} athletes into {ATHLETES_TABLE_NAME}...")
    now_iso = datetime.now(timezone.utc).isoformat()
    with athletes_table.batch_writer() as batch:
        for a in DEMO_ATHLETES:
            batch.put_item(
                Item={
                    "athlete_id": a["id"],
                    "athlete_name": a["name"],
                    "access_token": a["token"],
                    "clubs": [club],
                    "updated_at": now_iso,
                }
            )

    # Seed activities
    print(f"🏃 Seeding {len(ACTIVITY_TEMPLATES)} activities into {ACTIVITIES_TABLE_NAME}...")
    base_time = datetime.now(timezone.utc)
    total_km = 0.0

    with activities_table.batch_writer() as batch:
        for idx, (ath_id, title, act_type, km, time_s, elev, days_ago) in enumerate(ACTIVITY_TEMPLATES, 1):
            act_date = (base_time - timedelta(days=days_ago, hours=idx % 8, minutes=idx * 7)).strftime("%Y-%m-%dT%H:%M:%S")
            act_id = f"demo_act_{idx:04d}"
            dist_decimal = Decimal(str(round(km, 2)))
            total_km += km

            batch.put_item(
                Item={
                    "activity_id": act_id,
                    "athlete_id": ath_id,
                    "athlete": athlete_map.get(ath_id, "Unknown"),
                    "clubs": [club],
                    "title": title,
                    "type": act_type,
                    "sport_type": act_type,
                    "distance_km": dist_decimal,
                    "moving_time_seconds": int(time_s),
                    "total_elevation_gain": Decimal(str(elev)),
                    "start_date": act_date,
                }
            )

    print(f"✨ Successfully seeded {len(DEMO_ATHLETES)} athletes and {len(ACTIVITY_TEMPLATES)} activities ({total_km:.1f} total km).")
    return {
        "athletes_count": len(DEMO_ATHLETES),
        "activities_count": len(ACTIVITY_TEMPLATES),
        "total_km": round(total_km, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for PRE or DEV environments")
    parser.add_argument("--env", default="dev", choices=["dev", "pre"], help="Target environment")
    parser.add_argument("--club", default="almas_inquietas", help="Club ID to associate athletes and activities")
    parser.add_argument("--reset", action="store_true", help="Wipe target environment tables before seeding")

    args = parser.parse_args()
    seed(env=args.env, reset=args.reset, club=args.club)


if __name__ == "__main__":
    main()

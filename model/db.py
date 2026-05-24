# models/db.py
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import pandas as pd


MUNICIPALITIES = [
    "ALAMINOS",
    "BAY",
    "CABUYAO",
    "CALAUAN",
    "CAVINTI",
    "BINAN",
    "CALAMBA",
    "SAN PEDRO",
    "SANTA ROSA",
    "FAMY",
    "KALAYAAN",
    "LILIW",
    "LOS BANOS",
    "LUISIANA",
    "LUMBAN",
    "MABITAC",
    "MAGDALENA",
    "MAJAYJAY",
    "NAGCARLAN",
    "PAETE",
    "PAGSANJAN",
    "PAKIL",
    "PANGIL",
    "PILA",
    "RIZAL",
    "SAN PABLO",
    "SANTA CRUZ",
    "SANTA MARIA",
    "SINILOAN",
    "VICTORIA",
]


def get_dummy_historical_yield(municipality, year, season):
    """Return a stable sample yield for a municipality/year/season."""
    municipality_index = MUNICIPALITIES.index(municipality) + 1
    year_offset = year - 2018
    season_bonus = 0.24 if season == 2 else 0
    municipality_bonus = (municipality_index % 8) * 0.16
    small_variation = ((municipality_index * year * season) % 9) * 0.03

    return round(3.05 + year_offset * 0.08 + season_bonus + municipality_bonus + small_variation, 2)


def get_dummy_realtime_yield(municipality, phase):
    """Return a stable sample in-season predicted yield for real-time displays."""
    municipality_index = MUNICIPALITIES.index(municipality) + 1
    municipality_bonus = (municipality_index % 7) * 0.08
    phase_bonus = phase * 0.54

    return round(0.48 + phase_bonus + municipality_bonus, 2)


def seed_rice_fields(cursor, start_year=2018, end_year=2024):
    """Create one rice_field row per municipality/year/season."""
    for municipality in MUNICIPALITIES:
        for year in range(start_year, end_year + 1):
            for season in (1, 2):
                cursor.execute(
                    """
                    INSERT INTO rice_field (municipality, year, season)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (municipality, year, season) DO NOTHING
                    """,
                    (municipality, year, season),
                )


def seed_historical_dummy_data(cursor, start_year=2018, end_year=2024):
    """Add sample historical yield data for every seeded rice_field row."""
    for municipality in MUNICIPALITIES:
        for year in range(start_year, end_year + 1):
            for season in (1, 2):
                cursor.execute(
                    """
                    INSERT INTO historical (id_rice, yield)
                    SELECT id_rice, %s
                    FROM rice_field
                    WHERE municipality = %s AND year = %s AND season = %s
                    ON CONFLICT (id_rice) DO UPDATE
                    SET yield = EXCLUDED.yield
                    WHERE historical.yield IS NULL OR historical.yield = 0
                    """,
                    (
                        get_dummy_historical_yield(municipality, year, season),
                        municipality,
                        year,
                        season,
                    ),
                )


def seed_realtime_dummy_data(cursor, year=2024, season=2):
    """Add sample real-time phase rows for the latest seeded season."""
    phase_dates = (
        (1, f"{year}-04-20"),
        (2, f"{year}-06-20"),
        (3, f"{year}-08-20"),
    )

    for municipality in MUNICIPALITIES:
        for phase, sample_date in phase_dates:
            cursor.execute(
                """
                INSERT INTO real_time (id_rice, date, phase, season, yield)
                SELECT id_rice, %s, %s, %s, %s
                FROM rice_field
                WHERE municipality = %s AND year = %s AND season = %s
                ON CONFLICT (id_rice, date) DO UPDATE
                SET phase = EXCLUDED.phase,
                    season = EXCLUDED.season,
                    yield = EXCLUDED.yield
                WHERE real_time.yield IS NULL OR real_time.yield = 0
                """,
                (
                    sample_date,
                    phase,
                    season,
                    get_dummy_realtime_yield(municipality, phase),
                    municipality,
                    year,
                    season,
                ),
            )


def seed_dummy_data(conn, start_year=2018, end_year=2024):
    """Seed every application table with deterministic dummy data."""
    with conn.cursor() as cursor:
        seed_rice_fields(cursor, start_year, end_year)
        seed_historical_dummy_data(cursor, start_year, end_year)
        seed_realtime_dummy_data(cursor, year=end_year, season=2)


def get_table_counts(cursor):
    """Return row counts for the app tables."""
    counts = {}
    for table_name in ("rice_field", "historical", "real_time"):
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        counts[table_name] = cursor.fetchone()[0]

    return counts


# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    """Create and return a new PostgreSQL connection."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    return psycopg2.connect(database_url)


def initialize_database(start_year=2018, end_year=2024):
    """Create Render PostgreSQL tables and baseline rice field rows."""
    schema_path = Path(__file__).resolve().parents[1] / "data" / "laguna_crop_schema_postgres.sql"

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8"))
            seed_rice_fields(cursor, start_year, end_year)
            seed_historical_dummy_data(cursor, start_year, end_year)
            seed_realtime_dummy_data(cursor, year=end_year, season=2)

        conn.commit()
        with conn.cursor() as cursor:
            counts = get_table_counts(cursor)

        print(
            "Database schema and dummy data are ready. "
            f"rice_field={counts['rice_field']}, "
            f"historical={counts['historical']}, "
            f"real_time={counts['real_time']}."
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =========================
# HISTORICAL DATA
# =========================
def get_historical_data(year=None, season=None):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT rf.municipality, rf.year, rf.season, h.yield
        FROM historical h
        JOIN rice_field rf ON h.id_rice = rf.id_rice
    """
    params = []

    if year is not None and season is not None:
        query += " WHERE rf.year = %s AND rf.season = %s"
        params.extend([year, season])

    cursor.execute(query, params)
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return data


# =========================
# PHASE LOGIC
# =========================
def get_phase(day, month):
    if (month == 3 and day >= 16) or (4 <= month <= 9 and (month != 9 or day <= 15)):
        if (month == 3 and day >= 16) or month == 4 or (month == 5 and day <= 15):
            return 1
        elif (month == 5 and day >= 16) or month == 6 or (month == 7 and day <= 15):
            return 2
        elif (month == 7 and day >= 16) or month == 8 or (month == 9 and day <= 15):
            return 3
    else:
        if (month == 9 and day >= 16) or month == 10 or (month == 11 and day <= 15):
            return 1
        elif (month == 11 and day >= 16) or month == 12 or (month == 1 and day <= 15):
            return 2
        elif (month == 1 and day >= 16) or month == 2 or (month == 3 and day <= 15):
            return 3

    return None


# =========================
# STORE PREDICTION RESULT
# =========================
def store_prediction_result(result):
    city = result.get('City')
    day = int(result.get('Day'))
    month = int(result.get('Month'))
    predicted_yield = float(result.get('Predicted Yield'))

    phase = get_phase(day, month)

    season = 1 if (month >= 9 or month <= 3) else 2
    current_year = datetime.now().year

    correct_date = datetime(current_year, 1, 1) + pd.Timedelta(days=day - 1)
    correct_day = correct_date.day

    date_str = f"{current_year}-{month:02d}-{correct_day:02d}"

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Get rice field ID
        cursor.execute(
            "SELECT id_rice FROM rice_field WHERE municipality = %s",
            (city,)
        )
        row = cursor.fetchone()

        if not row:
            print(f"Warning: No rice_field record found for '{city}'. Skipping insertion.")
            return

        id_rice = row[0]

        # Check duplicate
        cursor.execute("""
            SELECT COUNT(*) FROM real_time
            WHERE id_rice = %s AND date = %s
        """, (id_rice, date_str))

        count = cursor.fetchone()[0]

        if count > 0:
            print(f"Skipping insertion: Data for '{city}' on {date_str} already exists.")
            return

        # Insert data
        cursor.execute("""
            INSERT INTO real_time (id_rice, date, phase, season, yield)
            VALUES (%s, %s, %s, %s, %s)
        """, (id_rice, date_str, phase, season, predicted_yield))

        conn.commit()
        print("Prediction result inserted successfully.")

    except Exception as e:
        conn.rollback()
        print("Error inserting prediction result:", e)

    finally:
        cursor.close()
        conn.close()


# =========================
# REAL-TIME DATA
# =========================
def get_realtime_yield_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
        SELECT rf.municipality, rt.yield
        FROM real_time rt
        JOIN rice_field rf ON rt.id_rice = rf.id_rice
        WHERE rt.date = (
            SELECT MAX(date)
            FROM real_time
            WHERE id_rice = rt.id_rice
        )
        ORDER BY rf.municipality ASC
        """

        cursor.execute(query)
        results = cursor.fetchall()

        if not results:
            return [], [], {}

        municipalities = [row[0] for row in results]
        yields = [row[1] if row[1] is not None else "No data" for row in results]
        yield_data = {row[0]: row[1] for row in results}

        return municipalities, yields, yield_data

    except Exception as e:
        print(f"Error fetching real-time data: {e}")
        return [], [], {}

    finally:
        cursor.close()
        conn.close()


# =========================
# MULTI-YEAR DATA
# =========================
def get_multi_year(season=None, municipalities=None):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT rf.municipality, rf.year, rf.season, h.yield
        FROM historical h
        JOIN rice_field rf ON h.id_rice = rf.id_rice
        WHERE 1=1
    """
    params = []

    if season is not None:
        query += " AND rf.season = %s"
        params.append(season)

    if municipalities:
        placeholders = ','.join(['%s'] * len(municipalities))
        query += f" AND rf.municipality IN ({placeholders})"
        params.extend(municipalities)

    query += " ORDER BY rf.municipality, rf.year"

    cursor.execute(query, params)
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return data


# =========================
# MUNICIPALITIES LIST
# =========================
def get_all_municipalities():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT municipality
        FROM rice_field
        ORDER BY municipality
    """)

    municipalities = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return municipalities

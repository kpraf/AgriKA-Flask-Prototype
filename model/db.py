# models/db.py
import os
import psycopg2
from datetime import datetime
import pandas as pd


# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    """Create and return a new PostgreSQL connection."""
    return psycopg2.connect(os.environ["postgresql://agrika_user:9zLg9OrIm3yQduyBqLDtBqDjlJoSwd9Y@dpg-d82670e7r5hc73e6h8fg-a/laguna_crop_yield"])


# =========================
# HISTORICAL DATA
# =========================
def get_historical_data(year=None, season=None):
    conn = get_db_connection()
    cursor = conn.cursor()

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
    cursor = conn.cursor()

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
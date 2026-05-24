import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model.db import seed_dummy_data


def connect():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set DATABASE_URL before running this script.")

    return psycopg2.connect(database_url)


def apply_schema(conn):
    schema_path = Path(__file__).resolve().parents[1] / "data" / "laguna_crop_schema_postgres.sql"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        schema_sql = schema_file.read()

    with conn.cursor() as cursor:
        cursor.execute(schema_sql)
    conn.commit()


def import_historical_csv(conn, csv_path):
    rows_imported = 0

    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as historical_file:
        reader = csv.DictReader(historical_file)
        required_headers = {"municipality", "year", "season", "yield"}
        missing_headers = required_headers - set(reader.fieldnames or [])
        if missing_headers:
            missing = ", ".join(sorted(missing_headers))
            raise RuntimeError(f"CSV is missing required column(s): {missing}")

        with conn.cursor() as cursor:
            for row in reader:
                municipality = row["municipality"].strip().upper()
                year = int(row["year"])
                season = int(row["season"])
                yield_value = float(row["yield"])

                cursor.execute(
                    """
                    INSERT INTO rice_field (municipality, year, season)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (municipality, year, season) DO UPDATE
                    SET municipality = EXCLUDED.municipality
                    RETURNING id_rice
                    """,
                    (municipality, year, season),
                )
                id_rice = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO historical (id_rice, yield)
                    VALUES (%s, %s)
                    ON CONFLICT (id_rice) DO UPDATE
                    SET yield = EXCLUDED.yield
                    """,
                    (id_rice, yield_value),
                )
                rows_imported += 1

    conn.commit()
    return rows_imported


def print_counts(conn):
    with conn.cursor() as cursor:
        for table in ("rice_field", "historical", "real_time"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Initialize the Render PostgreSQL database.")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--historical-csv", help="CSV with municipality,year,season,yield columns.")
    args = parser.parse_args()

    with connect() as conn:
        apply_schema(conn)
        seed_dummy_data(conn, args.start_year, args.end_year)

        if args.historical_csv:
            imported = import_historical_csv(conn, args.historical_csv)
            print(f"historical rows imported: {imported}")

        conn.commit()
        print_counts(conn)


if __name__ == "__main__":
    main()

import argparse
import csv
import os
from pathlib import Path

import psycopg2


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


def seed_rice_fields(conn, start_year, end_year):
    with conn.cursor() as cursor:
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
        seed_rice_fields(conn, args.start_year, args.end_year)

        if args.historical_csv:
            imported = import_historical_csv(conn, args.historical_csv)
            print(f"historical rows imported: {imported}")

        print_counts(conn)


if __name__ == "__main__":
    main()

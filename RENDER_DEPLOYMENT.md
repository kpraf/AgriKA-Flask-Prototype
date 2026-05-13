# Render Deployment Notes

## Web service

- Language: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app`
- Python version: controlled by `.python-version`

## Required environment variables

- `SECRET_KEY`
- `DATABASE_URL`
- `SENTINELHUB_INSTANCE_ID`
- `SENTINELHUB_CLIENT_ID`
- `SENTINELHUB_CLIENT_SECRET`

Use the Render Postgres internal database URL for `DATABASE_URL` when the web
service and database are in the same Render region.

## Database setup

`data/laguna_crop_schema_postgres.sql` contains the PostgreSQL schema expected by
the Flask app.

The older `data/laguna_crop_database.sql` file is MySQL syntax and should not be
run directly against Render Postgres.

Run this from a Render shell or any machine that has access to the database:

```bash
python scripts/setup_render_db.py
```

That command creates the tables and inserts the baseline `rice_field` rows for
all municipalities from 2018 through 2024.

To import historical yield values, prepare a CSV with these columns:

```csv
municipality,year,season,yield
ALAMINOS,2018,1,4.12
ALAMINOS,2018,2,3.98
```

Then run:

```bash
python scripts/setup_render_db.py --historical-csv data/historical_data.csv
```

`data/historical_data_template.csv` is a small example of the expected format.

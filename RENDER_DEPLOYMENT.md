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
- `AUTO_INIT_DB` can be left unset. It defaults to `true`.

Use the Render Postgres internal database URL for `DATABASE_URL` when the web
service and database are in the same Render region.

## Database setup

`data/laguna_crop_schema_postgres.sql` contains the PostgreSQL schema expected by
the Flask app.

The older `data/laguna_crop_database.sql` file is MySQL syntax and should not be
run directly against Render Postgres.

The app automatically creates the tables and inserts deterministic dummy data
for `rice_field`, `historical`, and `real_time` on startup when `AUTO_INIT_DB`
is unset or set to `true`. This works on Render's free tier because it does not
require Shell access.

If you have Shell access, you can also run the setup manually:

```bash
python scripts/setup_render_db.py
```

That command creates the tables and inserts dummy data for all application
tables. The seed covers all municipalities from 2018 through 2024 and adds
sample real-time phase rows for the latest seeded season.

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

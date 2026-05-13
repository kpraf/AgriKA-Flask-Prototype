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

Historical seed data still needs to be imported separately into `rice_field` and
`historical`.

CREATE TABLE IF NOT EXISTS rice_field (
    id_rice SERIAL PRIMARY KEY,
    municipality VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    season SMALLINT NOT NULL CHECK (season IN (1, 2)),
    UNIQUE (municipality, year, season)
);

CREATE TABLE IF NOT EXISTS real_time (
    id_real SERIAL PRIMARY KEY,
    id_rice INTEGER NOT NULL REFERENCES rice_field(id_rice) ON DELETE CASCADE,
    date DATE NOT NULL,
    phase SMALLINT CHECK (phase IN (1, 2, 3)),
    season SMALLINT CHECK (season IN (1, 2)),
    yield DOUBLE PRECISION,
    UNIQUE (id_rice, date)
);

CREATE TABLE IF NOT EXISTS historical (
    id_his SERIAL PRIMARY KEY,
    id_rice INTEGER NOT NULL REFERENCES rice_field(id_rice) ON DELETE CASCADE,
    yield DOUBLE PRECISION,
    UNIQUE (id_rice)
);

CREATE INDEX IF NOT EXISTS idx_rice_field_municipality
    ON rice_field (municipality);

CREATE INDEX IF NOT EXISTS idx_rice_field_year_season
    ON rice_field (year, season);

CREATE INDEX IF NOT EXISTS idx_real_time_id_rice_date
    ON real_time (id_rice, date);

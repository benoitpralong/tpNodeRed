CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS tag_values (
	time TIMESTAMPTZ NOT NULL DEFAULT now(),
	tag TEXT NOT NULL,
	value DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('tag_values', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS tag_values_tag_time_idx
	ON tag_values (tag, time DESC);
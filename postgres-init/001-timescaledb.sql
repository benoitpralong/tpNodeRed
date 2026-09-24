CREATE SEQUENCE IF NOT EXISTS demo_id_seq;

CREATE TABLE IF NOT EXISTS demo (
	id BIGINT PRIMARY KEY DEFAULT nextval('demo_id_seq'),
	texte TEXT NOT NULL
);

ALTER SEQUENCE demo_id_seq OWNED BY demo.id;
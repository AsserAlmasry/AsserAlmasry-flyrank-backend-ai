-- Runs once, the first time the Postgres volume is created
-- (mounted into /docker-entrypoint-initdb.d by docker-compose.yml).
CREATE TABLE IF NOT EXISTS tasks (
    id         SERIAL PRIMARY KEY,
    title      TEXT        NOT NULL CHECK (length(trim(title)) > 0),
    done       BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tasks (title, done) VALUES
    ('Read the assignment', TRUE),
    ('Build the CRUD API', FALSE),
    ('Push to GitHub', FALSE);

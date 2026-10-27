-- Stretch: one index + EXPLAIN ANALYZE before/after, on a seeded copy of the table.
DROP TABLE IF EXISTS tasks_bench;
CREATE TABLE tasks_bench (LIKE tasks INCLUDING DEFAULTS);
INSERT INTO tasks_bench (id, title, done)
SELECT g, 'task number ' || g, (g % 10 = 0) FROM generate_series(1, 200000) AS g;
ANALYZE tasks_bench;

\echo '--- BEFORE the index ---'
EXPLAIN ANALYZE SELECT * FROM tasks_bench WHERE title = 'task number 123456';

CREATE INDEX idx_tasks_bench_title ON tasks_bench (title);

\echo '--- AFTER the index ---'
EXPLAIN ANALYZE SELECT * FROM tasks_bench WHERE title = 'task number 123456';

DROP TABLE tasks_bench;

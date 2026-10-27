# BE-04 — Containerize your stack (Postgres + Docker Compose)

The Task API now stores its data in **PostgreSQL running in Docker**, and the whole stack (app + database + Redis) starts
with **one command**.

## Run it

Requirements: Docker Desktop (or Docker Engine with the compose plugin).

```bash
cd 03-docker-postgres
cp .env.example .env          # then change POSTGRES_PASSWORD (and the password in DATABASE_URL)
docker compose up --build
```

- API: <http://localhost:8000/tasks> · Swagger: <http://localhost:8000/docs>
- `GET /health` reports which storage is active and pings Redis:
  `{"status":"ok","storage":"PostgresTaskRepository","redis":"PONG"}`

Stop with `Ctrl-C` or `docker compose down`. **Never** use `docker compose down -v` unless you want to delete the data
volume.

## What is in the stack

| Service | Image | Job |
|---|---|---|
| `db` | `postgres:16-alpine` | The database. Data lives in the named volume `pgdata`. `db/init.sql` runs once, on a fresh volume, to create the table. |
| `app` | built from `Dockerfile` | FastAPI on port 8000. Waits for the database healthcheck before starting. |
| `redis` | `redis:7-alpine` | *(stretch)* ready for later weeks; the app pings it in `/health`. |

## Configuration (`.env`)

The connection string and credentials come from environment variables. `.env` is **gitignored**; `.env.example` is
committed with the same variable names and a placeholder password.

| Variable | Meaning |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Used by the Postgres container to create the user and database |
| `DATABASE_URL` | Used by the app. Inside compose the host is `db` (the service name); compose overrides it automatically |
| `STORAGE` | `postgres` (default) or `memory` |

## The architecture proving itself: one swap, routes unchanged

```
routes (app/main.py)  ->  TaskService (app/service.py)  ->  TaskRepository (interface)
                                                             ├── InMemoryTaskRepository   (app/repository.py)
                                                             └── PostgresTaskRepository   (app/postgres_repository.py)
```

Honest account of what changed when I switched storage (`git diff` of the "Stage 3b" commit):

- **Added** `app/postgres_repository.py`: the same five methods (`list / get / create / update / delete`) with the same
  return shapes, written in SQL.
- **Changed** in `app/main.py`: only the wiring at the top. A `build_repository()` function now picks the repository
  from the `STORAGE` env var.
- **Unchanged**: `app/service.py` (validation rules) and every route function. With `STORAGE=memory` the exact same routes
  run against the in-memory list.

## Persistence proof

How I checked: create rows → `docker compose down` (removes the app and database **containers**, keeps the volume) →
`docker compose up` → read them back through the API and straight from Postgres.

```text
POST /tasks {"title":"I must survive a restart"} -> {"id":4,...}
POST /tasks {"title":"Me too"}                   -> {"id":5,...}
PUT  /tasks/4 {"done":true}                      -> {"id":4,...,"done":true}

$ docker compose down && docker compose up -d

GET /tasks -> [... {"id":4,"title":"I must survive a restart","done":true}, {"id":5,"title":"Me too","done":false}]

$ docker compose exec db psql -U tasks -d tasks -c "SELECT id, title, done FROM tasks ORDER BY id;"
 id |          title           | done
----+--------------------------+------
  1 | Read the assignment      | t
  2 | Build the CRUD API       | f
  3 | Push to GitHub           | f
  4 | I must survive a restart | t
  5 | Me too                   | f
(5 rows)
```

Both the app container and the database container were destroyed and recreated, and the rows were still there. They live in
the `pgdata` volume, not in either container.

You can also start only the database, without compose: `./db/start-postgres.sh` (that was Stage 1).

## Stretch goals done

- **Redis** in the compose file, pinged from `/health` → `"redis":"PONG"`.
- **One index + `EXPLAIN ANALYZE`** on a seeded 200,000-row copy of the table ([`db/explain-index.sql`](db/explain-index.sql),
  full output in [`docs/explain-output.txt`](docs/explain-output.txt)):

| | Plan | Execution time |
|---|---|---|
| Before | `Seq Scan` — read all 200,000 rows, threw away 199,999 | **17.083 ms** |
| After `CREATE INDEX ... (title)` | `Index Scan using idx_tasks_bench_title` | **0.064 ms** |

That is roughly 270× faster for an exact title lookup. The trade-off is that every `INSERT`/`UPDATE` now also has to update
the index.

Run it yourself: `docker compose exec -T db psql -U tasks -d tasks < db/explain-index.sql`

#!/bin/bash
# Stage 1: run Postgres alone in Docker, with a named volume so data survives the container.
set -a; source "$(dirname "$0")/../.env"; set +a
docker run -d --name tasks-db \
  -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB="$POSTGRES_DB" \
  -p 5432:5432 -v tasks_pgdata:/var/lib/postgresql/data postgres:16-alpine

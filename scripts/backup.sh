#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

backup_dir=${1:-./backups}
mkdir -p "$backup_dir"
timestamp=$(date -u '+%Y%m%dT%H%M%SZ')

printf 'Backing up PostgreSQL database...\n'
docker compose -f docker-compose.yml exec -T db sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  > "$backup_dir/database-$timestamp.sql"

printf 'Backing up uploaded images...\n'
docker compose -f docker-compose.yml exec -T api \
  tar -czf - -C /app uploads \
  > "$backup_dir/uploads-$timestamp.tar.gz"

printf 'Backup complete: %s\n' "$backup_dir"

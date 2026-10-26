#!/bin/sh
# Run only in a dedicated development/test installation, never against customer production data.
set -eu
command -v docker >/dev/null 2>&1 || { echo 'Docker is required; no database tests have run.' >&2; exit 1; }
[ -f .env ] || python3 infra/init_env.py
docker compose build
docker compose up -d db storage
docker compose run --rm migrate
docker compose run --rm storage-init
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py spectacular --file /tmp/openapi.yaml --validate
docker compose run --rm -e RUN_STORAGE_TESTS=1 backend python manage.py test core crm business --noinput

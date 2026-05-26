#!/bin/sh
set -e

if [ -d /app/backend ]; then
  cd /app/backend
else
  cd backend
fi

python -m flask --app wsgi:app init-db >/dev/null 2>&1 || true
exec python worker.py
#!/bin/sh
set -e

if [ -d /app/backend ]; then
  cd /app/backend
else
  cd backend
fi

python -m flask --app wsgi:app init-db >/dev/null 2>&1 || true
exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} wsgi:app
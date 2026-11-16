#!/usr/bin/env bash
# Render start skripti. Free tarifda disk vaqtinchalik bo'lgani uchun
# migratsiya va superuser har ishga tushishda ham tekshiriladi.
set -o errexit
python manage.py migrate --no-input
python manage.py ensure_superuser
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60

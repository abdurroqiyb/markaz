#!/usr/bin/env bash
# Render build skripti: paketlar, static fayllar, migratsiya, superuser.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# SECRET_KEY muhitda bo'lmasa, .env fayliga avtomatik yoziladi (config/settings.py).
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py ensure_superuser

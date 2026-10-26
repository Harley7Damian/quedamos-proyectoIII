#!/usr/bin/env bash
# Comando de construccion para Render / Railway
set -o errexit
pip install -r requirements-prod.txt
python manage.py collectstatic --no-input
python manage.py migrate

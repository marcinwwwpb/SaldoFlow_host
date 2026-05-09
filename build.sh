#!/usr/bin/env bash
set -o errexit

python -m pip install -r requirements.txt
mkdir -p staticfiles
python manage.py collectstatic --noinput

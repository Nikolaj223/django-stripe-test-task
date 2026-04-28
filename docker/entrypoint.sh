#!/bin/sh
set -e

python manage.py migrate --noinput

python manage.py bootstrap_demo

python manage.py collectstatic --noinput

exec "$@"

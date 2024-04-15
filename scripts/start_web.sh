#!/bin/bash

# Make sure staticfiles are collected into the static volume
python3 manage.py collectstatic --noinput

# Make sure database is migrated
python3 manage.py migrate

# Start django server (ASGI)
daphne -b 0.0.0.0 -p 8000 amelie.asgi:application

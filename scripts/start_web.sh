#!/bin/bash

# Copy configuration to proper place
cp "/config/local.py" "/amelie/amelie/settings/local.py"

# Make sure staticfiles are collected into the static volume
python3 manage.py collectstatic --clear --noinput

# Make sure database is migrated
python3 manage.py migrate

# Start django server (ASGI)
daphne -b 0.0.0.0 -p 80  amelie.asgi:application

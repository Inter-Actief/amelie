#!/bin/bash

# Make sure staticfiles are collected into the static volume
python3 manage.py collectstatic --noinput

# Make sure database is migrated
python3 manage.py migrate

# Check if Django can run
python3 manage.py check

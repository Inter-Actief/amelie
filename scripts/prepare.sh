#!/bin/bash
echo "Preparing to run Amelie..."

# Make sure staticfiles are collected into the static volume
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Make sure database is migrated
echo "Migrating database..."
python3 manage.py migrate

# Check if Django can run
echo "Checking if Django can run..."
python3 manage.py check

echo "Done!"

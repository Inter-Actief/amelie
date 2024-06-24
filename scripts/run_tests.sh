#!/bin/bash

# Print some debugging information about the environment
# ------------------------------------------------------
# Python version
echo "Python version:"
python3 -V
# Path to the python binary being used
echo "Python binary:"
which python
# Pip version
echo "Pip version:"
pip -V
# Path to the pip binary being used
echo "Pip binary:"
which pip
# Installed pip package list
echo "Pip installed packages:"
pip freeze

# Configure Django and run the tests
# ----------------------------------
# Copy the test settings to local.py
echo "Copying test settings to local.py"
cp ./amelie/settings/tests.py ./amelie/settings/local.py

# Run Django initial checks
echo "Checking if Django can run..."
python3 manage.py check

# Make sure staticfiles are collected into the static volume
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Make sure database is migrated
echo "Executing Django migrations..."
python3 manage.py migrate

# Run Django tests
echo "Running Amelie tests..."
python3 manage.py test --keepdb

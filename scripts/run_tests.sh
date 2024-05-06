#!/bin/bash

# Print some debugging information about the environment
# ------------------------------------------------------
# Python version
python3 -V
# Path to the python binary being used
which python
# Pip version
pip -V
# Path to the pip binary being used
which pip
# Installed pip package list
pip freeze

# Configure Django and run the tests
# ----------------------------------
# Copy the test settings to local.py
cp ./amelie/settings/tests.py ./amelie/settings/local.py

# Run Django initial checks
python3 manage.py check

# Make sure staticfiles are collected into the static volume
python3 manage.py collectstatic --noinput

# Make sure database is migrated
python3 manage.py migrate

# Run Django tests
python3 manage.py test --keepdb

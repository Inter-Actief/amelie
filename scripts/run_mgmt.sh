#!/bin/bash

# Check if Django can run
echo "Checking if Django can run..."
python3 manage.py check

# Run the manage.py command
echo "Running management command '$@'..."
python3 manage.py "$@"

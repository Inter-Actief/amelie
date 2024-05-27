#!/bin/bash

# Check if Django can run
python3 manage.py check

# Run the manage.py command
python3 manage.py "$@"

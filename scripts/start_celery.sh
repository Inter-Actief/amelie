#!/bin/bash

# Copy configuration to proper place
cp "/config/local.py" "/amelie/amelie/settings/local.py"

# Extra command-line arguments to the worker:
# Jelte: Concurrency op 1 gezet, zodat er geen meerdere Claudia verify-calls tegelijk gaan lopen
# Jarmo: -E optie aangezet, zo geeft celery events door aan celerymon.

celery worker -n amelie1 -A amelie --time-limit=300 --concurrency=1 -E


#!/bin/bash

# Extra command-line arguments to the worker:
# Jelte: Concurrency op 1 gezet, zodat er geen meerdere Claudia verify-calls tegelijk gaan lopen
# Jarmo: -E optie aangezet, zo geeft celery events door aan celerymon.

echo "Starting celery worker..."
celery -A amelie worker -n amelie1 --time-limit=300 --concurrency=1 -E

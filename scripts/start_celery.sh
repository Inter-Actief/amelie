#!/bin/bash

# Extra command-line arguments to the worker:
# Jelte: Concurrency op 1 gezet, zodat er geen meerdere Claudia verify-calls tegelijk gaan lopen
# Jarmo: -E optie aangezet, zo geeft celery events door aan celerymon.
# Kevin: -Q optie meegeven, zo kunnen we meerdere workers starten voor verschillende queues (iamailer/claudia/overig)

# Parse queue argument from CLI
# No argument means default queue
if [ -z "$1" ]; then
    QUEUE="default"
# Valid queues are "mail", "claudia" and "default"
elif [ "$1" = "mail" ] || [ "$1" = "claudia" ] || [ "$1" = "default" ]; then
    QUEUE="$1"
# If an invalid queue is given, stop with an error.
else
    echo "Error: Invalid queue value '$1'. Valid values are: mail, claudia, default" >&2
    exit 1
fi

if [ -z "$HOSTNAME" ]; then
    echo "Error: Container has no HOSTNAME env variable set. A unique hostname is required for each Celery worker." >&2
    exit 1
fi

echo "Starting celery worker on $HOSTNAME for queue '$QUEUE'..."
celery -A amelie worker -n "$HOSTNAME-$QUEUE" -Q "$QUEUE" --time-limit=300 --concurrency=1 -E

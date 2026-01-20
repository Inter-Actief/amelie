#!/bin/bash

until timeout 10s celery -A amelie inspect ping; do
    >&2 echo "Celery workers not yet available"
done

echo "Starting flower celery dashboard..."
celery -A amelie flower

#!/bin/bash

echo "Starting flower celery dashboard..."
celery -A amelie flower

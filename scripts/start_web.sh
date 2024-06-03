#!/bin/bash

# Start django server (ASGI)
echo "Starting daphne server..."
daphne -b 0.0.0.0 -p 8000 amelie.asgi:application

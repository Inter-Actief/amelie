#!/bin/bash

# Start django server (WSGI)
echo "Starting uWSGI server..."
uwsgi --module=amelie.wsgi:application --http 0.0.0.0:8000 --workers 4 --threads 4 -b 32768 --master --vacuum --enable-threads --log-x-forwarded-for

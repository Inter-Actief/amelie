#!/bin/bash

# Start django server (WSGI)
echo "Starting uWSGI server..."
uwsgi --module=amelie.wsgi:application --master -s 0.0.0.0:8000 -p 4 --log-x-forwarded-for

#!/bin/bash

# Start django server (WSGI)
echo "Starting uWSGI server..."
uwsgi --module=amelie.wsgi:application --master -s 0.0.0.0:8080 -p 4 -t 60 --log-x-forwarded-for

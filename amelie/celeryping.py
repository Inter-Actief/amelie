# Basic Celery app configuration file for use in livenessProbes
# Uses the same environment variables also used in `amelie/settings/environ.py`
# Example use:
#   livenessProbe:
#     exec:
#       command:
#       - /bin/sh
#       - -c
#       - celery -A amelie.celeryping inspect ping -d celery@$HOSTNAME | grep -q OK
#     initialDelaySeconds: 60
#     periodSeconds: 30
#     timeoutSeconds: 300
#     successThreshold: 1
#     failureThreshold: 10

# Barebones Celery settings, just enough to make the `inspect ping` work.
import os
from celery import Celery

broker_url = os.getenv('DJANGO_CELERY_BROKER_URI', default='amqp://amelie:amelie@localhost:5672/amelie')
app = Celery('amelieping', broker=broker_url)
celery_app = app
app.conf.task_serializer = 'pickle'  # How to serialize the tasks
app.conf.accept_content = ['pickle']  # A list of content-types/serializers to allow

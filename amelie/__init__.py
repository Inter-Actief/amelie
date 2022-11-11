from __future__ import absolute_import

__author__ = "The WWW-committee of I.C.T.S.V. Inter-Actief"
__version__ = "2.0"

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
# Based on https://docs.celeryproject.org/en/latest/django/first-steps-with-django.html
from .celeryapp import app as celery_app  # noqa

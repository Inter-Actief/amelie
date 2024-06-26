from __future__ import absolute_import
# Settings used for running tests in Travis

# Load default settings
# noinspection PyUnresolvedReferences
from amelie.settings.generic import *

# Database
DATABASES = {
    'default': {
        'ENGINE': 'amelie.tools.utf8mb4_mysql_backend',
        'HOST': '172.17.0.1',
        'NAME': 'amelie_test',
        'USER': 'amelie_test',
        'PASSWORD': 'amelie_test',
        'OPTIONS': {'charset': 'utf8mb4'},
        'TEST': {
            'NAME': 'amelie_test',
        }
    }
}

SECRET_KEY = 'Cr38bXqNzU45MQx030enbqTyRZufMcywcRZJygkFKxnx5lu5Iq'

# Add Model Auth backend to allow logins to work in tests
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend'] + AUTHENTICATION_BACKENDS

# Disable secure redirects to allow testing without SSL
SECURE_SSL_REDIRECT = False

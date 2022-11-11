from __future__ import absolute_import
# Settings used for running tests in Travis

# Load default settings
# noinspection PyUnresolvedReferences
from amelie.settings import *

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'mariadb',
        'NAME': 'amelie_test',
        'USER': 'amelie_test',
        'PASSWORD': 'amelie_test',
    }
}

SECRET_KEY = 'Cr38bXqNzU45MQx030enbqTyRZufMcywcRZJygkFKxnx5lu5Iq'

# Disable secure redirects to allow testing without SSL
SECURE_SSL_REDIRECT = False

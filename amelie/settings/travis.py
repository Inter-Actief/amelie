from __future__ import absolute_import
# Settings used for running tests in Travis

# Load default settings
# noinspection PyUnresolvedReferences
from amelie.settings.generic import *

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'NAME': 'amelie_test',
        'USER': 'travis',
        'PASSWORD': '',
    }
}

SECRET_KEY = 'Cr38bXqNzU45MQx030enbqTyRZufMcywcRZJygkFKxnx5lu5Iq'

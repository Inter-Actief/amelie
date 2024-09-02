# This is configuration file for Amelie.
# This configuration file will load configuration from environment variables.

# Keep these imports here!
import warnings
import os
import json

import environ
from pathlib import Path

from email.utils import getaddresses
from django.core.management.utils import get_random_secret_key

from amelie.settings.generic import *

# Initialize an env object for `django-environ`
env = environ.Env()

# Proxy function for get_random_secret_key that replaces $ with % (because $ has a special function in django-environ)
def get_random_secret_key_no_dollar():
    s = get_random_secret_key()
    return s.replace('$', '%')

# Set base path of the project, to build paths with.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

# Configure database
DATABASES = {
    'default': env.db_url("DATABASE_URL", default=f"sqlite:////{BASE_DIR}/amelie.db")
}

# Override database engine to our custom mysql backend, if mysql database is used
if DATABASES['default'].get('ENGINE', None) == "django.db.backends.mysql":
    DATABASES['default']['ENGINE'] = 'amelie.tools.utf8mb4_mysql_backend'

# Override database options if environment variable is given (unsupported by django-environ's env.db() function)
DATABASE_OPTIONS = env.json('DATABASE_OPTIONS', default={})
if DATABASE_OPTIONS:
    DATABASES['default']['OPTIONS'] = DATABASE_OPTIONS

# Make sure these are set correctly in production
ENV                   = env('DJANGO_ENVIRONMENT', default='PRODUCTION')
DEBUG                 = env.bool('DJANGO_DEBUG', default=False)
DEBUG_TOOLBAR         = env.bool('DJANGO_DEBUG', default=False)
TEMPLATE_DEBUG        = env.bool('DJANGO_DEBUG', default=False)
MY_DEBUG_IN_TEMPLATES = False
IGNORE_REQUIRE_SECURE = False
PYDEV_DEBUGGER        = False
PYDEV_DEBUGGER_IP     = None

# Load the debug toolbar -- does not need to be changed in principle
if DEBUG_TOOLBAR:
    def custom_show_toolbar(request):
        return True

    # Order is important
    INSTALLED_APPS = INSTALLED_APPS + ('debug_toolbar',)
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': '%s.%s' % (__name__, custom_show_toolbar.__name__),
    }

# Do not redirect to HTTPS, because the nginx proxy container only listens on HTTP
SECURE_SSL_REDIRECT   = False

# Add allow cidr middleware as first middleware
MIDDLEWARE = ["allow_cidr.middleware.AllowCIDRMiddleware"] + MIDDLEWARE

# Allowed hosts -- localhost and 127.0.0.1 are always allowed, the rest comes from an environment variable.
ALLOWED_HOSTS = [
    "localhost", "127.0.0.1"
] + env.list("DJANGO_ALLOWED_HOSTS", default=[])

# Allowed CIDR nets -- for kubernetes internal services
ALLOWED_CIDR_NETS = ['172.30.0.0/16']
ALLOWED_CIDR_NETS.extend(env.list("DJANGO_ALLOWED_CIDR_NETS", default=[]))

# Add Kubernetes POD IP, if running in Kubernetes
KUBE_POD_IP = env("THIS_POD_IP", default="")
if KUBE_POD_IP:
  ALLOWED_CIDR_NETS.append(KUBE_POD_IP)

# Example: DJANGO_ADMINS="Jan Janssen <j.janssen@inter-actief.net>, Bob de Bouwer <b.bouwer@inter-actief.net>"
ADMINS = getaddresses([env("DJANGO_ADMINS", default="WWW-committee <amelie-errors@inter-actief.net>")])
MANAGERS = ADMINS

###
#  Logging settings
###
LOG_LEVEL = env("DJANGO_LOG_LEVEL", default="INFO")
LOG_LEVEL_CLAUDIA = env("DJANGO_LOG_LEVEL_CLAUDIA", default=LOG_LEVEL)

LOG_TO_CONSOLE = env.bool("DJANGO_LOG_TO_CONSOLE", default=True)
LOG_TO_FILE = env.bool("DJANGO_LOG_TO_FILE", default=False)
LOG_MAIL_ERRORS = env.bool("DJANGO_MAIL_ERRORS", default=False)

ENABLED_HANDLERS = []
ENABLED_HANDLERS_CLAUDIA = []
if LOG_TO_CONSOLE:
    ENABLED_HANDLERS.append('console')
    ENABLED_HANDLERS_CLAUDIA.append('console')
if LOG_TO_FILE:
    ENABLED_HANDLERS.append('amelie-file')
    ENABLED_HANDLERS_CLAUDIA.append('claudia-file')
if LOG_MAIL_ERRORS:
    ENABLED_HANDLERS.append('mail_admins')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s] %(levelname)s %(name)s %(funcName)s (%(filename)s:%(lineno)d) %(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        }
    },
    'handlers': {
        'amelie-file': {
            'level': LOG_LEVEL,
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': f'{BASE_DIR}/amelie.log',
            'formatter': 'verbose',
        },
        'claudia-file': {
            'level': LOG_LEVEL_CLAUDIA,
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': f'{BASE_DIR}/claudia.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': False,
        },
    },
    'root': { # all other errors go to the console, the general log file and sentry
        'level': 'DEBUG',
        'handlers': ENABLED_HANDLERS,
    },
    'loggers': {
        'amelie': { # Log all Amelie errors
            'level': 'DEBUG',
        },
        'amelie.claudia': { # store claudia logging in seperate file and log to eugenia
            'level': 'DEBUG',
            'handlers': ENABLED_HANDLERS_CLAUDIA,
            'propagate': False,
        },
        'django': { # Reset default settings for django
            'handlers': [],
        },
        'django.request': { # Reset default settings for django.request
            'handlers': [],
            'level': 'ERROR',
            'propagate': True,
        },
        'py.warnings': { # Reset default settings for py.warnings
            'handlers': [],
        },
        'sentry.errors': { # do not propagate sentry errors to sentry
            'level': 'DEBUG',
            'handlers': ENABLED_HANDLERS,
            'propagate': False,
        },
        'tornado.access': { # Ignore tornado.access INFO logging
            'handlers': [],
            'level': 'WARNING',
        },
        'amqp': { # Set AMQP to something else than debug (log spam)
            'level': 'WARNING',
        },
        'urllib3': { # Set urllib3 to something else than debug
            'level': 'WARNING',
        },
        'daphne': { # Set daphne logging to INFO
            'level': 'INFO'
        },
        # Ignore SAML2 errors due to unsollicited response error floods
        'saml2.entity': {'handlers': [], 'propagate': False},
        'saml2.client_base': {'handlers': [], 'propagate': False},
        'saml2.response': {'handlers': [], 'propagate': False},
        # Set OIDC logging to at least info due to process_request log flooding
        'mozilla_django_oidc.middleware': {'level': 'INFO'},
        # Set ModernRPC logging to at least info due to "register_method" log flooding for API
        'modernrpc.core': {'level': 'INFO'},
    },
}

# Sentry SDK configuration
DJANGO_SENTRY_DSN = env("DJANGO_SENTRY_DSN", default="")
DJANGO_SENTRY_ENVIRONMENT = env("DJANGO_SENTRY_ENVIRONMENT", default="production")
if DJANGO_SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=DJANGO_SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        # Proportion of requests that are traced for performance monitoring.
        # Keep at (or very very very close to) 0 in production!
        traces_sample_rate=0,
        # Send user details of request to Sentry
        send_default_pii=True,
        auto_session_tracking=False,
        environment=DJANGO_SENTRY_ENVIRONMENT,
    )


###
# Authentication settings
###

# Django authentication backends
# Login settings -- only allow login using specified backends
AUTHENTICATION_BACKENDS = env.list("DJANGO_AUTHENTICATION_BACKENDS", default=["django.contrib.auth.backends.ModelBackend"])

# OIDC Single sign-on configuration
OIDC_RP_CLIENT_ID = env("OIDC_RP_CLIENT_ID", default="amelie")
OIDC_RP_CLIENT_SECRET = env("OIDC_RP_CLIENT_SECRET", default="")


###
#  Keycloak settings
###
# Userinfo API configuration
USERINFO_API_CONFIG['api_key'] = env("AMELIE_USERINFO_API_KEY", default="")
USERINFO_API_CONFIG['allowed_ips'] = env.list("AMELIE_USERINFO_ALLOWED_IPS", default=[])

# Keycloak API secret
KEYCLOAK_API_CLIENT_SECRET = env("KEYCLOAK_API_CLIENT_SECRET", default="")


###
# Security settings
###

# Only use cookies for HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# If the proxy tells us the external side is HTTPS, use that
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Make this unique, and don't share it with anybody.
SECRET_KEY = env('DJANGO_SECRET_KEY', default=get_random_secret_key_no_dollar())


###
# Celery settings
###
# Setup broker for celery
CELERY_BROKER_URL = env('DJANGO_CELERY_BROKER_URI', default='amqp://amelie:amelie@localhost:5672/amelie')
BROKER_URL = CELERY_BROKER_URL  # Needed for django-health-check RabbitMQ check to work

# Django Celery -- True means that tasks will be executed immediately and are not queued!
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

if CELERY_BROKER_URL:
    # Add extra health checks if a celery broker is configured.
    INSTALLED_APPS = INSTALLED_APPS + (
        'health_check.contrib.celery_ping',  # requires celery, checks if workers are available
        'health_check.contrib.rabbitmq',     # requires RabbitMQ broker, checks if RabbitMQ is available
    )

###
#  Internationalization
###
gettext = lambda s: s # This way the below strings will be added to the 'translation list'
LANGUAGES = (
   ('nl', gettext('Nederlands')),
   ('en', gettext('Engels')),
)
LOCALE_PATHS = ('/amelie/locale', )


###
#  URL and Media settings
###
# Path to amelie static files
STATIC_ROOT = '/static'
STATIC_URL = env("AMELIE_STATIC_URL", default="/static/")

# Path to amelie media
MEDIA_ROOT = '/media'
MEDIA_URL = env("AMELIE_MEDIA_URL", default="/media/")

# Path to website (needed for pictures via the API among other things)
ABSOLUTE_PATH_TO_SITE = env("AMELIE_ABSOLUTE_PATH_TO_SITE", default="http://localhost:8080/")

# Method used for file download acceleration.
# Use None for no acceleration, "apache" for X-Sendfile header or "nginx" for X-Accel-Redirect header.
FILE_DOWNLOAD_METHOD = env("AMELIE_FILE_DOWNLOAD_METHOD", default="")


###
#  E-mail settings
###
EMAIL_BACKEND = env("AMELIE_EMAIL_BACKEND", default="django.core.mail.backends.filebased.EmailBackend")
EMAIL_HOST = env("AMELIE_EMAIL_HOST", default="smtp.snt.utwente.nl")


###
#  Claudia settings
###
# Default Plugins
CLAUDIA_ENABLE_DEFAULT_PLUGINS = env.bool("CLAUDIA_ENABLE_DEFAULT_PLUGINS", default=True)

CLAUDIA_PLUGINS = []
if CLAUDIA_ENABLE_DEFAULT_PLUGINS:
    CLAUDIA_PLUGINS.extend([
        'amelie.claudia.plugins.lognotices.LogNoticesPlugin',
        'amelie.claudia.plugins.timeline.TimelinePlugin',
    ])
CLAUDIA_PLUGINS.extend(env.list("CLAUDIA_ENABLED_PLUGINS", default=[]))

# Stop if an error is encountered
CLAUDIA_STOP_ON_ERROR = env.bool("CLAUDIA_STOP_ON_ERROR", default=False)

# Claudia Active Directory settings
CLAUDIA_AD['LDAP'] = env("CLAUDIA_AD_PROTOCOL", default=CLAUDIA_AD.get('LDAP', "ldaps"))
CLAUDIA_AD['HOST'] = env("CLAUDIA_AD_HOST", default=CLAUDIA_AD.get('HOST', ""))
CLAUDIA_AD['PORT'] = env.int("CLAUDIA_AD_PORT", default=CLAUDIA_AD.get('PORT', 636))
CLAUDIA_AD['USER'] = env("CLAUDIA_AD_USER", default=CLAUDIA_AD.get('USER', ""))
CLAUDIA_AD['PASSWORD'] = env("CLAUDIA_AD_PASSWORD", default=CLAUDIA_AD.get('PASSWORD', ""))
CLAUDIA_AD['BASEDN'] = env("CLAUDIA_AD_BASE_DN", default=CLAUDIA_AD.get('BASEDN', ""))
CLAUDIA_AD['CACERTFILE'] = env("CLAUDIA_AD_CA_CERT_FILE", default=CLAUDIA_AD.get('CACERTFILE', None))

# Claudia mail from address -- used as the From address of account management e-mails
CLAUDIA_MAIL['FROM'] = env("CLAUDIA_MAIL_FROM", default=CLAUDIA_MAIL.get('FROM', None))

# Claudia GitLab settings
CLAUDIA_GITLAB['TOKEN'] = env("CLAUDIA_GITLAB_TOKEN", default=CLAUDIA_GITLAB.get('TOKEN', None))

# Claudia GSuite settings
CLAUDIA_GSUITE['SERVICE_ACCOUNT_P12_FILE'] = env("CLAUDIA_GSUITE_SERVICE_ACCOUNT_P12_FILE", default=CLAUDIA_GSUITE.get('SERVICE_ACCOUNT_P12_FILE', None))
CLAUDIA_GSUITE['ALLOWED_ALIAS_DOMAINS'] = env.list("CLAUDIA_GSUITE_ALLOWED_ALIAS_DOMAINS", default=CLAUDIA_GSUITE.get('ALLOWED_ALIAS_DOMAINS', None))


###
#  Alexia settings
###
ALEXIA_API['URL'] = env("ALEXIA_API_URL", default=ALEXIA_API.get('URL', None))
ALEXIA_API['USER'] = env("ALEXIA_API_USERNAME", default=ALEXIA_API.get('USER', None))
ALEXIA_API['PASSWORD'] = env("ALEXIA_API_PASSWORD", default=ALEXIA_API.get('PASSWORD', None))

###
#  Twitter settings (probably broken due to twitter API changes)
###
TWITTER_APP_KEY = env("AMELIE_TWITTER_APP_KEY", default=TWITTER_APP_KEY)
TWITTER_APP_SECRET = env("AMELIE_TWITTER_APP_SECRET", default=TWITTER_APP_SECRET)
TWITTER_OAUTH_TOKEN = env("AMELIE_TWITTER_OAUTH_TOKEN", default=TWITTER_OAUTH_TOKEN)
TWITTER_OAUTH_SECRET = env("AMELIE_TWITTER_OAUTH_SECRET", default=TWITTER_OAUTH_SECRET)


###
#  Data Hoarder settings (GDPR data exporter)
###
DATA_HOARDER_CONFIG['key'] = env("DATA_HOARDER_KEY", default=DATA_HOARDER_CONFIG.get('key', None))
DATA_HOARDER_CONFIG['check_ssl'] = env.bool("DATA_HOARDER_CHECK_SSL", default=True)
DATA_HOARDER_CONFIG['export_basedir'] = env("DATA_HOARDER_EXPORT_BASEDIR", default="/homedir_exports")

# The location where data exports are saved until they expire
DATA_EXPORT_ROOT = "/data_exports"

###
#  Health check endpoint config
###
# URL token. Is included in the healthcheck URL, should be set to a unique value per environment.
HEALTH_CHECK_URL_TOKEN = env("HEALTH_CHECK_URL_TOKEN", default=HEALTH_CHECK_URL_TOKEN)

###
#  SysCom monitoring configuration (for room narrowcasting PC overview)
###
ICINGA_API_HOST = env("ICINGA_API_HOST", default=ICINGA_API_HOST)
ICINGA_API_USERNAME = env("ICINGA_API_USERNAME", default=ICINGA_API_USERNAME)
ICINGA_API_PASSWORD = env("ICINGA_API_PASSWORD", default=ICINGA_API_PASSWORD)


###
#  Spotify settings (for room narrowcasting music displays)
###
SPOTIFY_CLIENT_ID = env("SPOTIFY_CLIENT_ID", default=SPOTIFY_CLIENT_ID)
SPOTIFY_CLIENT_SECRET = env("SPOTIFY_CLIENT_SECRET", default=SPOTIFY_CLIENT_SECRET)
SPOTIFY_SCOPES = env("SPOTIFY_SCOPES", default=SPOTIFY_SCOPES)


###
#  Discord integration configuration
###
DISCORD["activities_webhooks"] = env.list("DISCORD_ACTIVITY_WEBHOOKS", default=[])
DISCORD["news_webhooks"] = env.list("DISCORD_NEWS_WEBHOOKS", default=[])
DISCORD["pictures_webhooks"] = env.list("DISCORD_PICTURES_WEBHOOKS", default=[])


###
# Cookie corner settings
###
# Id of DiscountPeriod-object for the free cookie discount
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_PERIOD_ID = env.int("COOKIE_CORNER_FREE_COOKIE_DISCOUNT_PERIOD_ID", default=0)

# Chances to win the Free Cookie Discount (0.0 = never, 1.0 = always)
# - First and second year students
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_LOW = env.float("COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_LOW", default=(1.0/20.0))

# - Older years and master students
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_HIGH = env.float("COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_HIGH", default=(1.0/20.0))

# -  Limit for the free cookie action (maximum amount of free cookies)
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_LIMIT = env.int("COOKIE_CORNER_FREE_COOKIE_DISCOUNT_LIMIT", default=30)

COOKIE_CORNER_POS_IP_ALLOWLIST = ['130.89.190.119', '2001:67c:2564:318:c7e6:7fe4:ad28:b5ef']
COOKIE_CORNER_POS_IP_ALLOWLIST.extend(env.list("COOKIE_CORNER_POS_IP_ALLOWLIST", default=[]))

# Maximum price of an activity
PERSONAL_TAB_MAXIMUM_ACTIVITY_PRICE = Decimal(env("PERSONAL_TAB_MAXIMUM_ACTIVITY_PRICE", default="50.00"))

# Cookie corner Wrapped
COOKIE_CORNER_WRAPPED_YEAR = env.int("COOKIE_CORNER_WRAPPED_YEAR", default=COOKIE_CORNER_WRAPPED_YEAR)


###
#  Amelie-specific settings
###
# Current theme for the website. Options: [None, "christmas", "valentine"]
WEBSITE_THEME_OVERRIDE = env("AMELIE_THEME_OVERRIDE", default=None)

# Youtube API key (for video module)
YOUTUBE_API_KEY = env("AMELIE_YOUTUBE_API_KEY", default="")

# FCM (Google Cloud Messaging) key
FCM_DJANGO_SETTINGS['FCM_SERVER_KEY'] = env("AMELIE_FCM_KEY", default="")

# Balcony duty week (0 is even weeks, 1 is uneven weeks)
BALCONY_DUTY_WEEK = env.int("AMELIE_BALCONY_DUTY_WEEK", default=0)

# Eventdesk from e-mail config
EVENT_DESK_FROM_EMAIL = env("AMELIE_EVENT_DESK_FROM_EMAIL", default=EVENT_DESK_FROM_EMAIL)

# Wo4you personal URL
BOOK_SALES_URL = env("AMELIE_BOOK_SALES_URL", default=BOOK_SALES_URL)

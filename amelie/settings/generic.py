# -*- coding: UTF-8 -*-

# Note: Imports cannot have a direct dependency on the settings below.
# Meaning, when a package is imported here, the initialization of that package cannot use the settings.
import os
import re
import saml2
from datetime import date
from decimal import Decimal

from django.views import debug

from saml2.saml import NAMEID_FORMAT_EMAILADDRESS, NAMEID_FORMAT_UNSPECIFIED
from saml2.sigver import get_xmlsec_binary

# In the passing of years a lot of settings have been added that contain confidential data.
# These settings need to be unreadable at all times, also in error reports, logs, etc.
# Unfortunately, Django's own regex is not extensive enough for this, so we add to it here.
debug.HIDDEN_SETTINGS = re.compile('TOKEN|PASS|KEY|SECRET|PROFANITIES_LIST|SIGNATURE')

# The base path to the Amelie project
BASE_PATH = os.path.join(os.path.dirname(__file__), '../..')

# Debug mode enabled setting
DEBUG = False

# Show the debug toolbar (DEBUG also needs to be True)
DEBUG_TOOLBAR = False

# Rosetta settings
ROSETTA_POFILE_WRAP_WIDTH = 0

# The current environment
ENV = 'PRODUCTION'

# Sizes of thumbnails that will be generated for pictures on the website
THUMBNAIL_SIZES = {
    'small': (256, 256),
    'medium': (800, 600),
    'large': (1600, 1200),
}

# Known mimetypes
MIMETYPES = {
    "image/jpeg": "image",
    "image/gif": "image",
    "image/png": "image",
    "image/tiff": "image",
    "application/pdf": "pdf",
    "appication/msword": "doc",
}

# The abbreviation of the Education Committee according to our models
EDUCATION_COMMITTEE_ABBR = "OnderwijsCommissie"

# The abbreviation for the System Administration Committee according to our models
SYSADMINS_ABBR = "Beheer"

# The Person ID of the person that is assigned to anonymized objects
ANONIMIZATION_SENTINEL_PERSON_ID = 4265

# E-mail address (fully qualified) of the Education Committee
EDUCATION_COMMITTEE_EMAIL = 'Onderwijscommissie Inter-Actief <oc@inter-actief.net>'

# The abbreviation of the Business Information Technology Bachelor Study according to our models
BIT_BSC_ABBR = 'B-BIT'

# The abbreviation of the Business Information Technology Master Study according to our models
BIT_MSC_ABBR = 'M-BIT'

# Category for pool committees
POOL_CATEGORY = "Pools"

# The direct debit debtor ID of Inter-Actief that needs to be printed on the autorization forms
DIRECT_DEBIT_DEBTOR_ID = 'NL81ZZZ400749470000'

# The LDAP host that is used to verify login attempts in the LDAP authentication module
LDAP_HOST = 'hexia.ia.utwente.nl'

# The RADIUS login details used to verify login attempts in the RADIUS authentication module
RADIUS_HOST = 'radius1.utsp.utwente.nl'
RADIUS_PORT = 1645
RADIUS_SECRET = b'etisbew_ai_www'
RADIUS_IDENTIFIER = 'interactief.utwente.nl'
RADIUS_DICT_LOCATION = os.path.join(BASE_PATH, 'amelie', 'tools', 'radius.dict')

# Caches that the website can use
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

# People that are notified of errors
ADMINS = (
    # ('WWW', 'amelie-errors@inter-actief.utwente.nl'),
)

# People who get broken link notifications when BrokenLinkEmailsMiddleware is enabled
MANAGERS = ADMINS

# Default 'from' email address to use for various automated correspondence
DEFAULT_FROM_EMAIL = 'ICTSV Inter-Actief <contact@inter-actief.net>'

# 'from' email address for errors when sentry cannot be reached
SERVER_EMAIL = 'amelie-errors@inter-actief.net'

# The e-mail backend and host to use
EMAIL_HOST = 'smtp.utwente.nl'
EMAIL_PORT = 25
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'  # Note that the default is a file backend!
EMAIL_TIMEOUT = 60.0 * 5  # Cut the connection with the mailserver after 5 minutes of inactivity
EMAIL_FILE_PATH = '/tmp/amelie-messages'  # The place to store the mail files when using a file backend
EMAIL_RETURN_PATH = '<bounces@inter-actief.net>'  # Where to send 'undeliverable' messages
EMAIL_REPORT_TO = 'WWW-commissie <www@inter-actief.net>'  # Where to send e-mail reports
EMAIL_INTERCEPT_ADDRESS = None
EMAIL_DELAY = 5  # Delay in seconds between consecutive mails

# Language code for this installation. All choices can be found here:
# https://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# https://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'nl'

gettext = lambda s: s  # To make sure the below strings are added to the 'translation list'

# Languages supported by this website
LANGUAGES = (
    ('nl', gettext('Dutch')),
    ('en', gettext('English')),
)

# The paths to search for locale files
LOCALE_PATHS = (os.path.join(BASE_PATH, 'locale'),)

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# To enable the formatting of numbers, this needs to be on
USE_L10N = True

# Absolute path to the directory that holds media and static files.
MEDIA_ROOT = os.path.join(BASE_PATH, 'site_media')
STATIC_ROOT = os.path.join(BASE_PATH, 'static')

# URL that handles the media served from MEDIA_ROOT and STATIC_ROOT.
MEDIA_URL = '/site_media/'
STATIC_URL = '/static/'

# CKEDITOR upload folder location in after MEDIA_URL
CKEDITOR_UPLOAD_PATH = "data/uploads/"
CKEDITOR_JQUERY_URL = "//ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'zva1y#$fsw+-=cpl5&)kj290i%pmd$v=a4^-1mk9uz2bzwl7f%'

# List of finder classes that know how to find static files in various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# The location where data exports are saved until they expire
DATA_EXPORT_ROOT = "/data/application_data/amelie/data_exports"

# Settings for the template renderer
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_PATH, 'templates')
        ],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'amelie.style.context_processors.basis_context',  # Injects the login form and oAuth login
                'amelie.style.context_processors.theme_context',  # Injects the website theme if one is active
                'amelie.api.context_processors.absolute_path_to_site',  # Injects the absolute path to the site for API
                'amelie.tools.context_processors.environment',  # Injects environment context
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                # 'django.template.loaders.eggs.Loader',
            ]
        }
    }
]

# Middleware classes that are used by the application
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'amelie.tools.cache.RequestCacheMiddleware',
    'amelie.tools.middleware.HttpResponseNotAllowedMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.admindocs.middleware.XViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'amelie.tools.middleware.PersonMiddleware',  # Adds person, is_board, is_education_committee attributes to request
    'auditlog.middleware.AuditlogMiddleware',
    'mozilla_django_oidc.middleware.SessionRefresh',  # Verify OIDC session tokens
]

# Authentication backends used by the application
AUTHENTICATION_BACKENDS = [
    'amelie.tools.auth.IAOIDCAuthenticationBackend',  # Logins via OIDC / auth.ia
]

# URL to the login page
LOGIN_URL = '/legacy_login/'

# URL that users are redirected to after login
LOGIN_REDIRECT_URL = '/'

# URL that users are redirected to after logout
LOGOUT_REDIRECT_URL = '/'

# Make the session expire when the browser closes by default
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# If indicated ('remember me'), keep the session for two weeks
SESSION_ALTERNATE_EXPIRE = 14 * 24 * 3600

# Prevent the site to be framed in other pages
X_FRAME_OPTIONS = 'DENY'

# The mail URL configuration file
ROOT_URLCONF = 'amelie.urls'

# List of sub-applications that are enabled.
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    # 'django.contrib.markup',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.admindocs',

    # Amelie apps
    'amelie.education',
    'amelie.members',
    'amelie.tools',
    'amelie.calendar',
    'amelie.activities',
    'amelie.news',
    'amelie.companies',
    'amelie.files',
    'amelie.about',
    'amelie.personal_tab',
    'amelie.twitter',
    'amelie.style',
    'amelie.narrowcasting',
    'amelie.api',
    'amelie.claudia',
    'amelie.iamailer',
    'amelie.weekmail',
    'amelie.room_duty',
    'amelie.gmm',
    'amelie.statistics',
    'amelie.blame',
    'amelie.videos',
    'amelie.oauth',
    'amelie.data_export',
    'amelie.publications',

    # JSONRPC API
    'modernrpc',

    # FCM (Firebase Cloud Messaging)
    'fcm_django',

    # YouTube API
    'googleapiclient',

    # Helpers
    'compressor',

    # Management of Amelie
    'django_extensions',

    # Add CORS headers for API
    'corsheaders',

    # Audit logging for various models
    'auditlog',

    # Things for the Oauth2 provider
    'oauth2_provider',

    # WYSIWYG Editor
    'ckeditor',
    'ckeditor_uploader',

    # SSL Runserver
    'sslserver',

    # OAuth2 Client
    'social_django',

    # Django-celery helper for celery results
    'django_celery_results',

    # SAML2 SP (authentication via UT)
    'djangosaml2',

    # SAML2 IdP
    'djangosaml2idp',
)

# Enable timezone support
USE_TZ = True

# Set the correct timezone
TIME_ZONE = 'Europe/Amsterdam'

# Allow dates to be in either dd-mm-yyyy or yyyy-mm-dd
DATE_INPUT_FORMATS = (
    # Supported formats:
    # dd-mm-yyyy
    # yyyy-mm-dd
    # dd/mm/yyyy
    # yyyy/mm/dd

    '%d-%m-%Y',
    '%Y-%m-%d',

    '%d/%m/%Y',
    '%Y/%m/%d',
)

# Allow times to be in either dd-mm-yy hh:ii:ss or yyyy-mm-dd hh:ii:ss
DATETIME_INPUT_FORMATS = (
    # Supported formats:
    # dd-mm-yyyy [hh[:ii[:ss]]]
    # yyyy-mm-dd [hh[:ii[:ss]]]
    # dd/mm/yyyy [hh[:ii[:ss]]]
    # yyyy/mm/dd [hh[:ii[:ss]]]

    '%d-%m-%Y %H:%M:%S',
    '%d-%m-%Y %H:%M',
    '%d-%m-%Y',

    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d',

    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
    '%d/%m/%Y',

    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%Y/%m/%d',
)

# Rename cookies to prevent collision with other Django installations on our webserver
CSRF_COOKIE_NAME = 'amelie_csrftoken'
LANGUAGE_COOKIE_NAME = 'amelie_django_language'
SESSION_COOKIE_NAME = 'amelie_sessionid'

# Allow Cross Origin requests, but only on the API.
CORS_ORIGIN_ALLOW_ALL = True
CORS_URLS_REGEX = r'^/api/.*$'

# Modules with JSONRPC API endpoints for autoregistration
MODERNRPC_METHODS_MODULES = [
    'amelie.api.api',
    'amelie.api.activitystream',
    'amelie.api.authentication',
    'amelie.api.committee',
    'amelie.api.company',
    'amelie.api.education',
    'amelie.api.narrowcasting',
    'amelie.api.news',
    'amelie.api.person',
    'amelie.api.personal_tab',
    'amelie.api.push',
    'amelie.api.videos'
]

MODERNRPC_HANDLERS = [
    "amelie.api.handlers.IAJSONRPCHandler"
]

# API documentation strings are formatted with markdown
MODERNRPC_DOC_FORMAT = 'markdown'

# Settings regarding direct debits
PERSONAL_TAB_MAXIMUM_ACTIVITY_PRICE = Decimal('30.00')  # Maximum price of an activity
PERSONAL_TAB_COMMITTEE_CAN_AUTHORIZE = True  # Allow the committee to enroll people that pay with their authorization

# Base path to the website. To be used when the django 'build_absolute_url()' does not work correctly.
ABSOLUTE_PATH_TO_SITE = "https://staging.ia.utwente.nl"

# IP addresses that are allowed to reach the Cookie Corner Point of Sale system
COOKIE_CORNER_POS_IP_ALLOWLIST = ('130.89.190.113', '2001:610:1908:1803:21b:21ff:fe01:87c2')

# The ID of the DiscountPeriod object of the Exam Cookie Discount
COOKIE_CORNER_EXAM_COOKIE_DISCOUNT_PERIOD_ID = 2

# The ID of the DiscountPeriod object of the Free Cookie Discount
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_PERIOD_ID = 3

# Chance to win the Free Cookie Discount (0.0 = never, 1.0 = always)
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_LOW = 0.0  # Chance for first and second year students
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_HIGH = 0.0  # Chance for older years and master students
COOKIE_CORNER_FREE_COOKIE_DISCOUNT_LIMIT = 0  # Limit for the free cookie action (maximum amount of free cookies)

# Conversion table from IBAN bank code to BIC
COOKIE_CORNER_BANK_CODES = {
    'ABNA': 'ABNANL2A',
    'AEGO': 'AEGONL2U',
    'ANAA': 'ANAANL21',
    'ANDL': 'ANDLNL2A',
    'ARBN': 'ARBNNL22',
    'ARSN': 'ARSNNL21',
    'ASNB': 'ASNBNL21',
    'ATBA': 'ATBANL2A',
    'BCDM': 'BCDMNL22',
    'BCIT': 'BCITNL2A',
    'BICK': 'BICKNL2A',
    'BINK': 'BINKNL21',
    'BKCH': 'BKCHNL2R',
    'BKMG': 'BKMGNL2A',
    'BLGW': 'BLGWNL21',
    'BMEU': 'BMEUNL21',
    'BNGH': 'BNGHNL2G',
    'BNPA': 'BNPANL2A',
    'BOFA': 'BOFANLNX',
    'BOFS': 'BOFSNL21002',
    'BOTK': 'BOTKNL2X',
    'BUNQ': 'BUNQNL2A',
    'CHAS': 'CHASNL2X',
    'CITC': 'CITCNL2A',
    'CITI': 'CITINL2X',
    'COBA': 'COBANL2X',
    'DEUT': 'DEUTNL2N',
    'DHBN': 'DHBNNL2R',
    'DLBK': 'DLBKNL2A',
    'DNIB': 'DNIBNL2G',
    'FBHL': 'FBHLNL2A',
    'FLOR': 'FLORNL2A',
    'FRGH': 'FRGHNL21',
    'FTSB': 'ABNANL2A',
    'FVLB': 'FVLBNL22',
    'GILL': 'GILLNL2A',
    'HAND': 'HANDNL2A',
    'HHBA': 'HHBANL22',
    'HSBC': 'HSBCNL2A',
    'ICBK': 'ICBKNL2A',
    'INGB': 'INGBNL2A',
    'INSI': 'INSINL2A',
    'ISBK': 'ISBKNL2A',
    'KABA': 'KABANL2A',
    'KASA': 'KASANL2A',
    'KNAB': 'KNABNL2H',
    'KOEX': 'KOEXNL2A',
    'KRED': 'KREDNL2X',
    'LOCY': 'LOCYNL2A',
    'LOYD': 'LOYDNL2A',
    'LPLN': 'LPLNNL2F',
    'MHCB': 'MHCBNL2A',
    'NNBA': 'NNBANL2G',
    'NWAB': 'NWABNL2G',
    'PCBC': 'PCBCNL2A',
    'RABO': 'RABONL2U',
    'RBOS': 'RBOSNL2A',
    'RBRB': 'RBRBNL21',
    'SNSB': 'SNSBNL2A',
    'SOGE': 'SOGENL2A',
    'STAL': 'STALNL2G',
    'TEBU': 'TEBUNL2A',
    'TRIO': 'TRIONL2U',
    'UBSW': 'UBSWNL2A',
    'UGBI': 'UGBINL2A',
    'VOWA': 'VOWANL21',
    'ZWLB': 'ZWLBNL21'
}

# Celery task scheduler settings
CELERY_TASK_ALWAYS_EAGER = True  # Always execute tasks in the foreground (blocking)
CELERY_TASK_EAGER_PROPAGATES = True  # If ALWAYS_EAGER, show the exceptions in the foreground
CELERY_SEND_TASK_ERROR_EMAILS = True  # Errors occurring during task execution will be sent to ADMINS by email
CELERY_TASK_SERIALIZER = 'pickle'  # How to serialize the tasks
CELERY_RESULT_BACKEND = 'django-db'  # Where to store the task results
CELERY_RESULT_SERIALIZER = 'pickle'  # How to serialize the task results
CELERY_ACCEPT_CONTENT = ['pickle']  # A list of content-types/serializers to allow
CELERY_BROKER_URL = None  # URL to the RabbitMQ broker (used when ALWAYS_EAGER is False)


# Connection settings for Alexia
ALEXIA_API = {
    'URL': 'https://alex.staging.ia.utwente.nl/api/1/',
    'USER': '',
    'PASSWORD': '',
    'ORGANIZATION': 'inter-actief'
}

# Login details for the University of Twente X (External) account of our association
X_ACCOUNT_USERNAME = ""
X_ACCOUNT_PASSWORD = ""

# Usernames (lowercase) that are not allowed to login to the website, even if they exist.
LOGIN_NOT_ALLOWED_USERNAMES = ["visitor", "gearloose", "ia_mediawiki", "ia_icinga", "bob", "beun"]

# Claudia plugins that are enabled
CLAUDIA_PLUGINS = (
    'amelie.claudia.plugins.lognotices.LogNoticesPlugin',  # Log events into a log file
    'amelie.claudia.plugins.timeline.TimelinePlugin',  # Maintain a timeline of events per object

    # 'amelie.claudia.plugins.aliases.AliasesPlugin',  # Maintains a list of aliases that should exist
    # 'amelie.claudia.plugins.wesp.WESPPlugin',  # Synchronize the aliases with WESP
    # 'amelie.claudia.plugins.accounts.AccountsPlugin',  # Manage Active Directory accounts and groups
    # 'amelie.claudia.plugins.gitlab_plugin.GitlabPlugin'  # Manage GitLab accounts and groups
    # 'amelie.claudia.plugins.mailnotify.MailNotifyPlugin',  # Notify admins of events
    # 'amelie.claudia.plugins.gsuite_plugin.GoogleSuitePlugin',  # Manages Google Suite accounts
)

# The Mapping ID for the Active Members mapping to which all active members are added
CLAUDIA_MAPPING_ACTIVE_MEMBERS = 439

# The Mapping ID for the Webmasters mapping that all webmasters in Django are added to
CLAUDIA_MAPPING_WEBMASTERS = 436

# Paths to available Unix shells (See also Person.SHELL_CHOICES)
CLAUDIA_SHELLS = {
    'bash': '/bin/bash',
    'zsh': '/bin/zsh',
}

# Default shell if the 'default' option is selected
CLAUDIA_SHELL_DEFAULT = 'bash'

# Make Claudia stop processing the queue if an error occurs
CLAUDIA_STOP_ON_ERROR = False

# Claudia's connection details to Active Directory
CLAUDIA_AD = {
    'LDAP': 'ldaps',
    'HOST': 'hexia.ia.utwente.nl',
    'PORT': 636,
    'USER': 'claudia',
    'PASSWORD': '',
    'BASEDN': 'ou=Inter-Actief,dc=ia,dc=utwente,dc=nl',
}

# Claudia's connection details to GitLab
CLAUDIA_GITLAB = {
    'SERVER': 'https://gitlab.ia.utwente.nl',
    'TOKEN': 'secret',
    'VERIFY_SSL': False
}

# Claudia: Connection to GSuite
CLAUDIA_GSUITE = {
    'PRIMARY_DOMAIN': "inter-actief.net",
    'OLD_BOARD_DOMAIN': "inter-actief.nl",
    # Mapping ID of the mapping that contains the members that need to sign in to their .nl account instead of .net
    'OLD_BOARD_MAPPING_ID': 2193,
    'ALLOWED_ALIAS_DOMAINS': ["inter-actief.net", "inter-actief.nl"],
    'DOMAIN_ADMIN_ACCOUNT_EMAIL': "claudia@inter-actief.nl",
    'SERVICE_ACCOUNT_EMAIL': "amelie-claudia@amelie-claudia.iam.gserviceaccount.com",
    'SERVICE_ACCOUNT_P12_FILE': "credentials/amelie-claudia-a1d089be2a09.p12",
    'SCOPES': {
        'DOMAIN_API': [
            'https://www.googleapis.com/auth/admin.directory.group',
            'https://www.googleapis.com/auth/admin.directory.group.member',
            'https://www.googleapis.com/auth/admin.directory.group.member.readonly',
            'https://www.googleapis.com/auth/admin.directory.group.readonly',
            'https://www.googleapis.com/auth/admin.directory.user',
            'https://www.googleapis.com/auth/admin.directory.user.alias',
            'https://www.googleapis.com/auth/admin.directory.user.alias.readonly',
            'https://www.googleapis.com/auth/admin.directory.user.readonly',
            'https://www.googleapis.com/auth/admin.directory.user.security',
            'https://www.googleapis.com/auth/admin.directory.userschema',
            'https://www.googleapis.com/auth/admin.directory.userschema.readonly'
        ],
        'GMAIL_API': [
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.settings.basic',
            'https://www.googleapis.com/auth/gmail.settings.sharing'
        ],
        'GROUPSSETTINGS_API': [
            'https://www.googleapis.com/auth/apps.groups.settings'
        ],
        'DRIVE_API': [
            'https://www.googleapis.com/auth/drive'
        ],
    }
}

# Claudia's connection details to WESP
CLAUDIA_WESP = {
    'USER': 'xmlrpcapi@interactief',
    'PASSWORD': 'secret',
    'DOMAIN': 'inter-actief.utwente.nl',
    'USECACHE': True,
    'DRYRUN': True,
}

# Claudia's e-mail client settings to send out account-related e-mails
CLAUDIA_MAIL = {
    'ENABLED': False,
    'FROM': 'Systeembeheer Inter-Actief <accountbeheer@inter-actief.net>',
    'SMTP_HOST': 'smtp.utwente.nl',
    'SMTP_PORT': 25,
    'SMTP_LOCALHOST': 'ia-beta.ia.utwente.nl',

    # Log complete text of each mail
    'LOG_MAIL': False,
}

# Irker settings to publish notifications to via IRC
IRKER_URL = ""
IRKER_PORT = 6659
IRKER_IRC_URL = ""
IRKER_CHANNEL = ""
IRKER_CHANNEL_KEY = ""
IRKER_CLAUDIA_CHANNEL = ""
IRKER_CLAUDIA_CHANNEL_KEY = ""

# Settings for the discord integration to publish notifications to
DISCORD = {
    "activities_webhooks": [],
    "news_webhooks": [],
    "pictures_webhooks": [],
}

# Settings for Firebase Cloud Messaging library
FCM_DJANGO_SETTINGS = {
    'FCM_SERVER_KEY': '',
    'DELETE_INACTIVE_DEVICES': True,
}

# Twitter keys and tokens for 'iawebsite'
TWITTER_APP_KEY = "empty"
TWITTER_APP_SECRET = "empty"
TWITTER_OAUTH_TOKEN = "empty"
TWITTER_OAUTH_SECRET = "empty"

# Settings for our oAuth2 provider
OAUTH2_PROVIDER = {
    'SCOPES': {
        'account': gettext('Access to your name, date of birth, student number, mandate status and committee status.'),
        'signup': gettext('Access to enrollments for activities and (un)enrolling you for activities.'),
        'transaction': gettext('Access to transactions, direct debit transactions, mandates and RFID-cards.'),
        'education': gettext('Access to complaints and sending or supporting complaints in your name.')
    },
    'ALLOWED_REDIRECT_URI_SCHEMES': ['http', 'https', 'iapp', 'inter-actief'],

    # refresh tokens remain valid for 1 month
    # expired refresh tokens and access tokens are cleared with the ``cleartokens`` command
    'REFRESH_TOKEN_EXPIRE_SECONDS': 2630000,
}

# SAML2 Identity Provider configuration
SAML_BASE_URL = "https://www.inter-actief.utwente.nl/saml2idp"
SAML_IDP_CONFIG = {
    'debug': 0,
    'xmlsec_binary': get_xmlsec_binary(['/opt/local/bin', '/usr/bin/xmlsec1']),
    'entityid': '%s/metadata' % SAML_BASE_URL,
    'description': 'Inter-Actief SAML IdP',

    'service': {
        'idp': {
            'name': 'Inter-Actief SAML IdP',
            'endpoints': {
                'single_sign_on_service': [
                    ('%s/sso/post' % SAML_BASE_URL, saml2.BINDING_HTTP_POST),
                    ('%s/sso/redirect' % SAML_BASE_URL, saml2.BINDING_HTTP_REDIRECT),
                ],
            },
            'name_id_format': [NAMEID_FORMAT_EMAILADDRESS, NAMEID_FORMAT_UNSPECIFIED],
            'sign_response': True,
            'sign_assertion': True,
        },
    },

    'metadata': {
        'local': [
            os.path.join(os.path.dirname(__file__), "../../certificates/google-sp-metadata.xml"),
            os.path.join(os.path.dirname(__file__), "../../certificates/google-ianl-sp-metadata.xml"),
            os.path.join(os.path.dirname(__file__), "../../certificates/google-ianet-sp-metadata.xml")
        ],
    },
    # These need to be valid certificates for Google! Self signed certs do not work!
    # Signing
    'key_file': '/etc/ia/key.ia.utwente.nl.pem',
    'cert_file': '/etc/ia/cert.ia.utwente.nl.pem',
    # Encryption
    'encryption_keypairs': [{
        'key_file': '/etc/ia/key.ia.utwente.nl.pem',
        'cert_file': '/etc/ia/cert.ia.utwente.nl.pem',
    }],
    'valid_for': 365 * 24,
}


# Configuration for the SAML service providers that need to authenticate to this IdP.
SAML_IDP_SPCONFIG = {
    'google.com': {
        'processor': 'amelie.tools.saml_processors.AmelieActiveMembersProcessor',
        # Attribute mapping from Django to SAML (e.g. {django: saml})
        'attribute_mapping': {}
    },
    'google.com/a/inter-actief.net': {
        'processor': 'amelie.tools.saml_processors.AmelieActiveMembersProcessor',
        # Attribute mapping from Django to SAML (e.g. {django: saml})
        'attribute_mapping': {}
    },
    'google.com/a/inter-actief.nl': {
        'processor': 'amelie.tools.saml_processors.AmelieActiveMembersProcessor',
        # Attribute mapping from Django to SAML (e.g. {django: saml})
        'attribute_mapping': {}
    }
}

# Module path to the view function to be used when an incoming request is rejected by the CSRF protection.
CSRF_FAILURE_VIEW = 'amelie.views.csrf_failure'

# Date on which old (pre-SEPA) authorizations are registered
DATE_PRE_SEPA_AUTHORIZATIONS = date(2009, 11, 1)

# Which runner to use to run the django tests
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Default primary key field type to use for models
# This will change to BigAutoField in the future so it is set to the old value here to avoid future unwanted migrations.
# TODO: We might want to look into migrating our current fields to BigAutoField at some point - albertskja 21-05-2021
# See https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Fix for https://github.com/certifi/python-certifi/issues/26
# Needed as long as openssl < 1.0.2
import os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

# CKEDITOR Config
CKEDITOR_UPLOAD_SLUGIFY_FILENAME = False
CKEDITOR_CONFIGS = {
    'default': {
        'skin': 'moono',
        'toolbar_Default': [
            {'name': 'document', 'items': ['Source', '-', 'Preview', '-', 'Templates']},
            {'name': 'clipboard', 'items': ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo']},
            {'name': 'editing', 'items': ['Find', 'Replace', '-', 'SelectAll']},
            '/',
            {'name': 'basicstyles',
             'items': ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript', '-', 'RemoveFormat']},
            {'name': 'paragraph',
             'items': ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Blockquote', 'CreateDiv', '-',
                       'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock', '-', 'BidiLtr', 'BidiRtl',
                       'Language']},
            {'name': 'links', 'items': ['Link', 'Unlink', 'Anchor']},
            '/',
            {'name': 'styles', 'items': ['Styles', 'Format', 'Font', 'FontSize']},
            {'name': 'colors', 'items': ['TextColor', 'BGColor']},
            {'name': 'tools', 'items': ['Maximize', 'ShowBlocks']},
            {'name': 'insert', 'items': ['Smiley', 'SpecialChar']},
            {'name': 'about', 'items': ['About']},
        ],
        'toolbar': 'Default',
        'tabSpaces': 4,
        'extraPlugins': ','.join(
            [
                # your extra plugins here
                'div',
                'autolink',
                'autoembed',
                'embedsemantic',
                'autogrow',
                # 'devtools',
                'widget',
                'lineutils',
                'clipboard',
                'dialog',
                'dialogui',
                'elementspath'
            ]),
        'templates_files': [STATIC_URL + 'js/templates.js'],
        'templates_replaceContent': False,
        'filebrowserBrowseUrl': '',
        'filebrowserImageBrowseUrl': '',
        'filebrowserFlashBrowseUrl': ''
    }
}

# ID for the youtube playlist that us used to auto-recommend new videos in the video module
YOUTUBE_UPLOADS_LIST_ID = 'UUyggWvLxjV1qv_rzg2ks-IA'

# Youtube API key to retrieve video information from for the video module
YOUTUBE_API_KEY = ''

# Domains that are not allowed to be set as an e-mail address domain in the website to avoid e-mail loops
IA_MAIL_DOMAIN = [
    '@inter-actief.utwente.nl',
    '@ia.utwente.nl',
    '@inter-actief.net',
    '@inter-actief.nl',
]

# Topics that can be selected when sending the push notifications
PUSH_TOPICS = [
    'news',
    'complaints',
    'activities',
]

# Settings for the homedir data exporter
DATA_HOARDER_CONFIG = {
    "url": "https://files.ia.utwente.nl:2715",  # No trailing slash!
    "key": "secret",
    "export_basedir": "/data/homedir_exports",
    "check_ssl": True,
}

USERINFO_API_CONFIG = {
    'api_key': None,
    'allowed_ips': [],
}

# Settings for Streaming.IA integration
STREAMING_BASE_URL = "https://streaming.ia.utwente.nl"  # No trailing slash!

# The special theme of the website, for special occasions. This overrides the theme of the website for everyone!
# Default: None (will use the normal theme). Options: ["christmas", "valentine"]
WEBSITE_THEME_OVERRIDE = None

# The week that IA has balcony duty.
# 0 means the even calendar weeks, 1 means the odd calendar weeks.
BALCONY_DUTY_WEEK = 0

# The e-mail address that eventdesk notices are sent to (must be an e-mailbox within the GSuite domain)
EVENT_DESK_NOTICES_EMAIL = "event_notices@inter-actief.net"
# The e-mail address that is shown on the eventdesk page on the site, where new registrations should be sent to
EVENT_DESK_NOTICES_DISPLAY_EMAIL = "events@inter-actief.net"
# The e-mail address that eventdesk notices are sent from
EVENT_DESK_FROM_EMAIL = "events@utwente.nl"
# The Label ID of the label that processed e-mails should get
EVENT_DESK_PROCESSED_LABEL_ID = "Label_5424798960935964974"
# The Label ID of the label that e-mails with errors should get
EVENT_DESK_ERROR_LABEL_ID = "Label_5802521922307679990"

# The Icinga (Monitoring) host and details (ask the system administrators), used for the room narrowcasting page.
ICINGA_API_HOST = "https://monitoring.ia.utwente.nl:5665/v1/"
ICINGA_API_USERNAME = "iawebsite"
ICINGA_API_PASSWORD = ""
ICINGA_API_SSL_VERIFY = True

# The Spotify app details for the room narrowcasting page.
SPOTIFY_CLIENT_ID = "19f600baa77b4223b639088daa62f2f2"
SPOTIFY_CLIENT_SECRET = ""
SPOTIFY_SCOPES = "user-read-currently-playing"

# Date on which old RFID cards are registered. Old RFID cards were registered before we kept track of registration date.
DATE_OLD_RFID_CARDS = date(2019, 9, 1)

# Default setting for enabling profiling (the rest of the config is done in local.py(.default)
# If this is turned on a lot of data will be generated and stored in the database. So only turn it on if you feel bold.
ENABLE_REQUEST_PROFILING = False

# Security headers, https://internet.nl/
SECURE_SSL_REDIRECT = True  # Enable HTTPS redirect
SECURE_REFERRER_POLICY = 'same-origin'  # No referrer to external parties
SECURE_HSTS_SECONDS = 31536000  # HSTS TTL
SECURE_CONTENT_TYPE_NOSNIFF = True

# Single Sign On via https://auth.ia.utwente.nl/
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/auth"
OIDC_OP_TOKEN_ENDPOINT = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/userinfo"
OIDC_RP_CLIENT_ID = "amelie-beta"
OIDC_RP_CLIENT_SECRET = "secret"
# Our custom Auth Backend will take care of creating users
OIDC_CREATE_USER = False
# Allows logout via GET request insitead of just POST
ALLOW_LOGOUT_GET_METHOD = True
# Keycloak uses RS256 sigining, so we need to specify that and provide the JWKS endpoint for key verification
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/certs"
OIDC_LOGOUT_URL = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/logout"

# Keycloak API -- auth.ia
KEYCLOAK_API_BASE = "https://auth.ia.utwente.nl/admin/realms"
KEYCLOAK_REALM_NAME = "inter-actief"
KEYCLOAK_API_CLIENT_ID = "admin-cli"
KEYCLOAK_API_CLIENT_SECRET = ""
KEYCLOAK_API_AUTHN_ENDPOINT = "https://auth.ia.utwente.nl/realms/inter-actief/protocol/openid-connect/token"

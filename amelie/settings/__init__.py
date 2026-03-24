from amelie.settings.generic import *

# Try to import local settings, fallback to config via environment variables if that fails
try:
	from amelie.settings.local import *
except ImportError:
	from amelie.settings.environ import *

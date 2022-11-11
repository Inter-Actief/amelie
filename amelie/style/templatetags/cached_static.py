import os

from django import template
from django.conf import settings


register = template.Library()


@register.simple_tag
def cached_static(path):
    """
    Returns absolute URL to static file with caching.
    """
    full_path = os.path.join(settings.STATIC_ROOT, path)
    try:
        # Get file modification time
        mod_time = os.path.getmtime(full_path)
        return '%s%s?%s' % (settings.STATIC_URL, path, mod_time)
    except OSError:
        # Returns normal url if this file was not found in filesystem
        return '%s%s' % (settings.STATIC_URL, path)

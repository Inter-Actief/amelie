from django.conf import settings

from amelie.forms import AmelieAuthenticationForm
from amelie.tools.http import is_allowed_ip


def basis_context(request):
    return {
        'form_login': AmelieAuthenticationForm(),
        'show_oauth': 'no_oauth' not in request.GET,
    }


def theme_context(request):
    ip_has_themes_disabled, _ = is_allowed_ip(request, allowed_ips=settings.BLOCKED_THEME_IP_RANGES)
    if ip_has_themes_disabled:
        return {'theme': None}
    return {'theme': settings.WEBSITE_THEME_OVERRIDE}

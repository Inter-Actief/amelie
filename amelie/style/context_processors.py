import ipaddress

from django.conf import settings

from amelie.forms import AmelieAuthenticationForm


def basis_context(request):
    return {
        'form_login': AmelieAuthenticationForm(),
        'show_oauth': 'no_oauth' not in request.GET,
    }


def theme_context(request):
    if not ip_blocked(request):
        return {'theme': settings.WEBSITE_THEME_OVERRIDE}
    else:
        return {'theme': None}


def ip_blocked(request):
    ip = request.META.get("REMOTE_ADDR", "")
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any(ip_obj in net for net in settings.BLOCKED_THEME_IP_RANGES)
    except ValueError:
        return False



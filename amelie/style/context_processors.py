from django.conf import settings

from amelie.forms import AmelieAuthenticationForm
from amelie.tools.http import client_has_themes_disabled


def basis_context(request):
    return {
        'form_login': AmelieAuthenticationForm(),
        'show_oauth': 'no_oauth' not in request.GET,
    }


def theme_context(request):
    if not client_has_themes_disabled(request):
        return {'theme': None}
    return {'theme': settings.WEBSITE_THEME_OVERRIDE}

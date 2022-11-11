from django.conf import settings

from amelie.forms import AmelieAuthenticationForm


def basis_context(request):
    return {
        'form_login': AmelieAuthenticationForm(),
        'show_oauth': 'no_oauth' not in request.GET,
    }


def theme_context(request):
    return {'theme': settings.WEBSITE_THEME_OVERRIDE}

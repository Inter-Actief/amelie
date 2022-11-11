from django import template

register = template.Library()


@register.filter
def provider_name(provider):
    providers = {
        'google-oauth2': 'Google',
        'github': 'GitHub',
        'linkedin-oauth2': 'LinkedIn',
        'facebook': 'Facebook'
    }

    if not isinstance(provider, str):
        if hasattr(provider, 'title'):
            provider = provider.title

        if hasattr(provider, 'name'):
            provider = provider.name

    return providers.get(provider.lower(), None)

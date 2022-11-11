from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def active_menu(context, needle, haystack=None, css_class='active'):
    import re

    # Request is necessary!
    if 'request' not in context:
        return ''

    # Setup the haystack
    haystack = haystack if haystack else (context['request'].path if hasattr(context['request'], 'path') else '')

    # Search for needle in haystack
    if re.search(str(needle).lower(), str(haystack).lower()):
        return css_class

    # No match
    return ''

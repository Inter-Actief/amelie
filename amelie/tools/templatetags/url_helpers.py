from django import template
from django.http import QueryDict
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def update_query_string(context, *args, **kwargs):
    # Grab GET parameters
    request = context['request']
    get = request.GET.copy() if request.GET else QueryDict('').copy()

    # Add new parameters
    for key, value in kwargs.items():
        if type(value) == list:
            get.update({key: value})
        else:
            get[key] = value

    # Convert to URL part
    return get.urlencode()


@register.simple_tag
def promo_url(page):
    if not page:
        return reverse('narrowcasting:promo_list')
    return reverse('narrowcasting:promo_list', kwargs={'page': page, })

import datetime

from django import template

from amelie.companies.models import WebsiteBanner

register = template.Library()


@register.inclusion_tag('banners.html')
def banners(amount):
    """
    Get a number of random banners.
    """
    return {
        'banners': WebsiteBanner.objects.filter(active=True, start_date__lte=datetime.date.today(),
                                                end_date__gte=datetime.date.today()).order_by('?')[:amount]
    }

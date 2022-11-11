from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.filter
def date_short(date):
    return render_to_string('date_short.html', {'date': date})


@register.filter
def date_long(date):
    return render_to_string('date_long.html', {'date': date})


@register.filter
def is_today(date):
    import datetime

    return date.date() == datetime.date.today()


@register.filter
def is_in_the_past(date):
    from datetime import datetime

    return date < datetime.now()

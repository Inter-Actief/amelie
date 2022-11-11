from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def transaction_link(context, date_from=None, date_to=None):
    current_view = context['view_name']
    person = context['person']
    params = {}

    app = context['request'].resolver_match.app_name

    if current_view == 'personal_tab:person_transactions':
        params['pk'] = person.pk
        params['slug'] = person.slug

    if date_from and date_to:
        params['date_from'] = date_from
        params['date_to'] = date_to

    return reverse(current_view, kwargs=params, current_app=app)


@register.simple_tag(takes_context=True)
def exam_cookie_credit_link(context, date_from=None, date_to=None):
    current_view = context['view_name']
    person = context['person']
    params = {}

    app = context['request'].resolver_match.app_name

    if current_view == 'personal_tab:person_exam_cookie_credit':
        params['person_id'] = person.id
        params['slug'] = person.slug

    if date_from and date_to:
        params['date_from'] = date_from
        params['date_to'] = date_to

    return reverse(current_view, kwargs=params, current_app=app)

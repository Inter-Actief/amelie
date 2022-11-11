from django import template

register = template.Library()


@register.filter(name='extend')
def extend(value, lists):
    for val in value:
        yield(val)

    for list in lists:
        yield(list)

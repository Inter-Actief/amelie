from django import template

register = template.Library()


@register.filter
def get_help_text(model, field):
    return model._meta.get_field(field).help_text

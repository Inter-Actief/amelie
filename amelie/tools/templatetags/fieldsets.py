import copy
from collections import OrderedDict

from django import template

"""
Source: https://djangosnippets.org/snippets/1019/

Simple tag to split an existing form into multiple fieldsets, wile keeping the original form configuration.

Syntax: {% get_fieldset list,of,fields as new_form_object from original_form %}

"""

register = template.Library()


def fieldset(parser, token):
    try:
        name, fields, as_, variable_name, from_, form = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError('Bad arguments for %r' % token.split_contents()[0])

    return FieldSetNode(fields.split(','), variable_name, form)


fieldset = register.tag(fieldset)


class FieldSetNode(template.Node):
    def __init__(self, fields, variable_name, form_variable):
        self.fields = fields
        self.variable_name = variable_name
        self.form_variable = form_variable

    def render(self, context):
        form = template.Variable(self.form_variable).resolve(context)
        new_form = copy.copy(form)
        new_form.fields = OrderedDict([(key, value) for key, value in form.fields.items() if key in self.fields])

        context[self.variable_name] = new_form

        return ''

from django import template
from django.utils.html import linebreaks

register = template.Library()


@register.tag
def htmlify(parser, token):
    nodelist = parser.parse(('endhtmlify',))
    parser.delete_first_token()
    return HTMLifyNode(nodelist)


class HTMLifyNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    """
    Renders this subject node like a comment, but adds the subject to the context
    """
    def render(self, context):
        text = self.nodelist.render(context)
        if context.get('render_type', '') == 'text/html':
            text = linebreaks(text)

        return text

from django import template

register = template.Library()


@register.tag('onlyhtml')
def only_html(parser, token):
    nodelist = parser.parse(('endonlyhtml',))
    parser.delete_first_token()
    return OnlyNode(nodelist, "text/html")


@register.tag('onlyplain')
def only_plain(parser, token):
    nodelist = parser.parse(('endonlyplain',))
    parser.delete_first_token()
    return OnlyNode(nodelist, "text/plain")


class OnlyNode(template.Node):
    def __init__(self, nodelist, render_type):
        self.nodelist = nodelist
        self.render_type = render_type
    def render(self, context):
        output = ''
        if context.get('render_type', '') == self.render_type:
            output = self.nodelist.render(context)

        return output

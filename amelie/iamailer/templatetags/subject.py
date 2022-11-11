from django import template

register = template.Library()


@register.tag
def subject(parser, token):
    nodelist = parser.parse(('endsubject',))
    parser.delete_first_token()
    return SubjectNode(nodelist)


class SubjectNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    """
    Renders this subject node like a comment, but adds the subject to the context
    """
    def render(self, context):
        subject = self.nodelist.render(context)
        context["subject"] = subject
        return ''

from hashlib import md5

from django import template
from django.contrib.staticfiles import finders
from django.template.base import TemplateSyntaxError
from django.templatetags.static import StaticNode

register = template.Library()


@register.tag
def attach_static(parser, token):
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("'{}' takes exactly one argument (static filename)".format(bits[0]))

    staticfilename = parser.compile_filter(bits[1])
    return AttachStaticNode(staticfilename)


class AttachStaticNode(template.Node):
    def __init__(self, staticfilename):
        self.staticfilename = staticfilename

    def render(self, context):
        staticfilename = self.staticfilename.resolve(context)

        # Check if the static file exists
        if not finders.find(staticfilename):
            raise TemplateSyntaxError("Static file {} could not be found.".format(staticfilename))

        cid = md5(staticfilename.encode()).hexdigest()
        context["attach_static"][cid] = staticfilename

        if context.get("render_preview", False):
            node = StaticNode(path=self.staticfilename)
            return node.render(context)

        return "cid:{}".format(cid)

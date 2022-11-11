from urllib.parse import urljoin

from django import template
from django.conf import settings
from django.template.base import TemplateSyntaxError
from django.template.defaulttags import URLNode

register = template.Library()


@register.tag
def absolute_url(parser, token):
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("'{}' takes exactly one argument (viewname)".format(bits[0]))

    urlname = parser.compile_filter(bits[1])
    return AbsoluteNode(urlname)


class AbsoluteNode(URLNode):
    def __init__(self, urlname):
        super(AbsoluteNode, self).__init__(urlname, [], {}, None)
        self.urlname = urlname

    def render(self, context):
        relative = super(AbsoluteNode, self).render(context)

        return urljoin(settings.ABSOLUTE_PATH_TO_SITE, relative)


@register.tag
def absolute_link(parser, token):
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("'{}' takes exactly one argument (url)".format(bits[0]))

    relative_url = parser.compile_filter(bits[1])
    return AbsoluteLinkNode(relative_url)


class AbsoluteLinkNode(template.Node):
    def __init__(self, relative_url):
        self.relative_url = relative_url

    def render(self, context):
        relative = self.relative_url.resolve(context)
        return urljoin(settings.ABSOLUTE_PATH_TO_SITE, relative)

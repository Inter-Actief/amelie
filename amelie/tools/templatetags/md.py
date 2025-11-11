import logging
from urllib.parse import urlparse, urlunparse

from django import template
from django.conf import settings
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe

import markdown as md
import nh3

register = template.Library()

logger = logging.getLogger(__name__)


class AbsoluteURLsProcessor(md.treeprocessors.Treeprocessor):
    def fix_link(self, link):
        base_url = urlparse(settings.ABSOLUTE_PATH_TO_SITE)
        url = urlparse(link)

        if not url.path:
            return link  # Bail, as the link might be a fragment link on the current page

        return urlunparse((
            url.scheme or base_url.scheme,
            url.netloc or base_url.netloc,
            url.path,
            url.params,
            url.query,
            url.fragment
        ))

    def fix_node(self, node):
        if node.tag == "a" and "href" in node.attrib:
            node.attrib["href"] = self.fix_link(node.attrib["href"])

        if node.tag == "img" and "src" in node.attrib:
            node.attrib["src"] = self.fix_link(node.attrib["src"])

        for child in node:
            self.fix_node(child)

    def run(self, root):
        self.fix_node(root)


class AbsoluteURLExtension(md.Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(AbsoluteURLsProcessor(md), 'absoluteURLs', 175)


class RemoveURLProcessor(md.treeprocessors.Treeprocessor):
    def fix_link(self, link):
        base_url = urlparse(settings.ABSOLUTE_PATH_TO_SITE)
        url = urlparse(link)

        if not url.path:
            return link  # Bail, as the link might be a fragment link on the current page

        return urlunparse((
            url.scheme or base_url.scheme,
            url.netloc or base_url.netloc,
            url.path,
            url.params,
            url.query,
            url.fragment
        ))

    def fix_node(self, node):
        if node.tag == "a" and "href" in node.attrib:
            del node.attrib["href"]
            node.tag = "span"

        for child in node:
            self.fix_node(child)

    def run(self, root):
        self.fix_node(root)


class RemoveURLExtension(md.Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(RemoveURLProcessor(md), 'removeURLs', 175)


def markdown(value, arg=""):
    extras = [e.strip() for e in arg.split(",") if e.strip()]

    safe_mode = True
    extensions = []

    if "unsafe" in extras:
        safe_mode = False

    if "absolute_urls" in extras:
        extensions.append(AbsoluteURLExtension())

    if "remove_urls" in extras:
        extensions.append(RemoveURLExtension())

    if safe_mode:
        value = nh3.clean(value, tags=[], attributes={})

    result = md.markdown(force_str(value), extensions=extensions)

    return mark_safe(result)


markdown.is_safe = True
register.filter(markdown)

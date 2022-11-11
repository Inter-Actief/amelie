from __future__ import division, absolute_import, print_function, unicode_literals

import logging

import dateutil.parser
from bs4 import BeautifulSoup
from markdown import markdown

logger = logging.getLogger(__name__)


def parse_datetime(dtstring):
    """
    Parse a datetime in ISO 8601 format.
    :param str|unicode dtstring: ISO 8601 formatted datetime.
    :return: Parsed datetime object.
    :rtype: datetime.datetime
    """
    dt = dateutil.parser.parse(dtstring)
    if dt.tzinfo is None:
        raise ValueError('Received datetime without timezone: %s' % dtstring)
    return dt


def strip_markdown(markdowntext):
    """
    Strip markdown formatting.

    Strips markdown formatting by first converting it to HTML and then removing the HTML tags.

    :param str|unicode markdowntext: Input text.
    :return: Text without markdown formatting.
    :rtype: unicode
    """
    return ''.join(BeautifulSoup(markdown(markdowntext), "html.parser").findAll(text=True))

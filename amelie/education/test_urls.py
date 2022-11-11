from __future__ import unicode_literals

from amelie.tools.tests import UrlsTestCase


class BaseUrlsTestCase(UrlsTestCase):
    url_names = [
        'education:overview',
        'education:news_archive',

        'education:complaints',
        'education:complaint_new',
        'education:course_new',

        'education:bouquet',

        'education:category_new',

        'education:page_new',

        'education:event_overview',
        'education:event_new',
    ]

BaseUrlsTestCase.generateMethods()

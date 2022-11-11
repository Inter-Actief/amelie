from __future__ import unicode_literals

from amelie.tools.tests import UrlsTestCase


class BaseUrlsTestCase(UrlsTestCase):
    url_names = [
        # Site workings
        'profile_overview',
        'profile_edit',

        # General views
        'frontpage',
        # 'amelie.views.statistics',

        # API-like things
        'feeds:latest-news',
        'feeds:activities',
    ]


BaseUrlsTestCase.generateMethods()

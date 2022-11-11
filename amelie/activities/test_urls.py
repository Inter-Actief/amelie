from __future__ import unicode_literals

from amelie.tools.tests import UrlsTestCase


class ActivitiesUrlsTestCase(UrlsTestCase):
    url_names = [
        # URLs that are not about a specific activity
        'activities:activities',
        'activities:activities_old',
        # URLs about the (photo)gallery
        # 'activities:random_photo',
        'activities:photo_upload',

        # URLs about an activity
        'activities:new',

        # URLs about calendars
        'activities:activities_ics',
    ]

ActivitiesUrlsTestCase.generateMethods()

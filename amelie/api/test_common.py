from __future__ import division, absolute_import, print_function, unicode_literals

import datetime

import pytz
from django.test import testcases

from amelie.api.common import parse_datetime


class ParseDatetimeTest(testcases.SimpleTestCase):

    def test_zone_no_colon(self):
        """
        Test the parse_datetime() function with timezone information without colon (+0100).
        """
        dtinput = '2016-02-06T23:59:59+0800'
        tz = pytz.FixedOffset(8*60)
        expected = datetime.datetime(2016, 2, 6, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2017-01-16T23:59:59+0100'
        tz = pytz.FixedOffset(1*60)
        expected = datetime.datetime(2017, 1, 16, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2016-12-31T23:59:59-0600'
        tz = pytz.FixedOffset(-6*60)
        expected = datetime.datetime(2016, 12, 31, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2016-12-31T23:59:59+0000'
        tz = pytz.FixedOffset(0)
        expected = datetime.datetime(2016, 12, 31, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

    def test_zone_with_colon(self):
        """
        Test the parse_datetime() function with timezone information with colon (+01:00).
        """
        dtinput = '2016-02-06T23:59:59+08:00'
        tz = pytz.FixedOffset(8*60)
        expected = datetime.datetime(2016, 2, 6, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2017-01-16T23:59:59+01:00'
        tz = pytz.FixedOffset(1*60)
        expected = datetime.datetime(2017, 1, 16, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2016-12-31T23:59:59-06:00'
        tz = pytz.FixedOffset(-6*60)
        expected = datetime.datetime(2016, 12, 31, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

        dtinput = '2016-12-31T23:59:59+00:00'
        tz = pytz.FixedOffset(0)
        expected = datetime.datetime(2016, 12, 31, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

    def test_zone_z(self):
        """
        Test the parse_datetime() function with UTC timezone labeled with Z.
        """
        dtinput = '2016-12-31T23:59:59Z'
        tz = pytz.FixedOffset(0)
        expected = datetime.datetime(2016, 12, 31, 23, 59, 59, tzinfo=tz)
        self.assertEqual(parse_datetime(dtinput), expected)

    def test_no_zone(self):
        """
        Test the parse_datetime() function without timezone information.
        """
        dtinput = '2016-04-27T02:07:51'
        self.assertRaisesMessage(ValueError, 'Received datetime without timezone: 2016-04-27T02:07:51', parse_datetime,
                                 dtinput)

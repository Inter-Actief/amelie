from __future__ import division, absolute_import, print_function, unicode_literals

import datetime

from django.utils import timezone
from oauth2_provider.models import AccessToken

from amelie.tools.tests import APITestCase


class CheckAuthTokenTest(APITestCase):

    def test_check_auth_token_valid(self):
        """
        Test the checkAuthToken() call with valid tokens.
        """
        self.send_and_compare_request('checkAuthToken', [], self.data['token1'], True)
        self.send_and_compare_request('checkAuthToken', [], self.data['token2'], True)

    def test_check_auth_token_unexisting(self):
        """
        Test the checkAuthToken() call with unexisting tokens.
        """
        self.send_and_compare_request('checkAuthToken', [], '', False)
        self.send_and_compare_request('checkAuthToken', [], 'null', False)
        self.send_and_compare_request('checkAuthToken', [], '6Jfmd2Zu022VLT4gf4na', False)

    def test_check_auth_token_expired(self):
        """
        Test the checkAuthToken() call with expired tokens.
        """
        now = timezone.now()
        anhourago = now - datetime.timedelta(hours=1)

        token = 'RZ4o9v5ASVOrEr5Z4Yyi'
        accesstoken = AccessToken(user=self.data['user2'], token=token, application=self.data['application1'],
                                  expires=anhourago)
        accesstoken.save()

        self.send_and_compare_request('checkAuthToken', [], token, False)

from __future__ import division, absolute_import, print_function, unicode_literals

import datetime
import json

from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.test import Client, testcases
from django.test.utils import override_settings, modify_settings
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken

from amelie.members.models import Person, Committee, Preference, PreferenceCategory, Membership, MembershipType, Function
from amelie.tools.logic import current_association_year
from amelie.tools.models import Profile


class SimpleTestCase(testcases.SimpleTestCase):
    # Use long messages on failure
    longMessage = True
    # Do not limit diff length on failure
    maxDiff = None

    def assertJSONEqual(self, raw, expected_data, msg=None):
        if not isinstance(expected_data, str):
            # Encode non-string input as JSON to fix a bug timestamps not comparing equal.
            expected_data = json.dumps(expected_data, cls=DjangoJSONEncoder)

        super(SimpleTestCase, self).assertJSONEqual(raw, expected_data, msg)

    def convertAndAssertJSONEqual(self, data, expected_data, msg=None):
        """
        Converts the data to JSON and asserts that the JSON fragments equals the expected_data.
        Usual JSON non-significant whitespace rules apply as the heavyweight
        is delegated to the json library.
        """

        super(SimpleTestCase, self).assertJSONEqual(json.dumps(data, cls=DjangoJSONEncoder), expected_data, msg)


class TransactionTestCase(SimpleTestCase, testcases.TransactionTestCase):
    pass


class TestCase(TransactionTestCase, testcases.TestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        self.data = dict()

    def isodate_param(self, dt):
        """
        Convert datetime to isodate for use as API parameter.

        Requires timezone to be UTC.
        :param datetime.datetime dt: datetime to format.
        :return: Formatted datetime
        :rtype: str
        """

        self.assertEqual(dt.utcoffset(), datetime.timedelta(), "Timezone of isodate_param parameter not UTC")

        return dt.replace(microsecond=0).isoformat().replace('+00:00', '+0000')

    def load_basic_data(self):
        data = self.data

        # User
        username1 = 'testuser'
        username2 = 'testuser2'

        data['password1'] = 'testuser13475'
        data['password2'] = 'testuser23475'

        data['user1'] = User(username=username1, is_superuser=True)
        data['user1'].set_password(data['password1'])
        data['user1'].save()

        data['person1'] = Person(first_name='Test', last_name='Client', gender=Person.GenderTypes.MAN, user=data['user1'],
                                  account_name=data['user1'].username)
        data['person1'].save()

        data['user2'] = User(username=username2, first_name='Test2', last_name='Client', email='test2@example.com')
        data['user2'].set_password(data['password2'])
        data['user2'].save()

        data['person2'] = Person(first_name='Test2', last_name='Client', gender=Person.GenderTypes.MAN, user=data['user2'],
                                  account_name=data['user2'].username)
        data['person2'].save()

        # Committee
        data['committee1'] = Committee(name='Committee 1', abbreviation='Com1')
        data['committee1'].save()

        # Preference
        preference_category = PreferenceCategory(name='Test')
        preference_category.save()
        Preference(name='mail_send_invite', category=preference_category).save()

        # Application
        data['application1'] = Application(user=data['user1'],
                                           client_type=Application.CLIENT_CONFIDENTIAL,
                                           authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
                                           name='Legacy getAuthToken API token')
        data['application1'].save()

        # AccessToken
        now = timezone.now()
        anhourahead = now + datetime.timedelta(hours=1)

        data['token1'] = '8BfvC6TIzFyGiiSrjQy9'
        data['accesstoken1'] = AccessToken(user=data['user1'], token=data['token1'], application=data['application1'],
                                           expires=anhourahead, scope='signup')
        data['accesstoken1'].save()

        data['token2'] = 'pRZEsWb5MQ93jaI1TAMX'
        data['accesstoken2'] = AccessToken(user=data['user2'], token=data['token2'], application=data['application1'],
                                           expires=anhourahead)
        data['accesstoken2'].save()


class APITestCase(TestCase):
    def setUp(self):
        super(APITestCase, self).setUp()

        self.load_basic_data()

        # Every test needs a client.
        self.client = Client()

    def send_request(self, method, params, token):
        """
        Send JSON RPC method call.
        :param method: Name of method to call.
        :param params: Parameters for JSON RPC call.
        :rtype : django.http.response.HttpResponse
        """
        path = reverse('api:jsonrpc_mountpoint')

        req = {
            'jsonrpc': '1.0',
            'id': 'jsonrpc',
            'method': method,
            'params': params,
        }

        req_json = json.dumps(req)

        if token is not None:
            response = self.client.post(path, req_json, content_type='text/plain; charset=UTF-8',
                                        HTTP_AUTHORIZATION='Bearer %s' % token)
        else:
            response = self.client.post(path, req_json, content_type='text/plain; charset=UTF-8')

        self.assertEqual(response['Content-Type'], 'application/json-rpc')

        content = response.content.decode()

        return response, content

    def send_and_compare_request(self, method, params, token, expected_result):
        """
        Send JSON RPC method call and compare actual result with expected result.
        :param method: Name of method to call.
        :param params: Parameters for JSON RPC call.
        :param expected_result: Expected result.
        """
        response, content = self.send_request(method, params, token)

        expected_data = {
            'jsonrpc': '1.0',
            'id': 'jsonrpc',
            'error': None,
            'result': expected_result,
        }

        self.assertJSONEqual(content, expected_data)

    def send_and_compare_request_error(self, method, params, token, error_code, error_name, error_message,
                                       error_data=None, status_code=200):
        """
        Send JSON RPC method call and compare actual error result with expected error result.
        :param method: Name of method to call.
        :param params: Parameters for JSON RPC call.
        :param error_code: Expected error code.
        :param error_name: Expected error name.
        :param error_message: Expected error message.
        :param error_data: Expected error data.
        :param status_code: Expected HTTP status code.
        """
        response, content = self.send_request(method, params, token)

        self.assertEqual(response.status_code, status_code,
                         'HTTP status code invalid. Content: ' + content)

        expected_data = {
            'jsonrpc': '1.0',
            'id': 'jsonrpc',
            'error': {
                'code': error_code,
                'name': error_name,
                'message': error_message,
                'data': error_data,
            },
            'result': None,
        }

        self.assertJSONEqual(content, expected_data, 'JSON RPC result')


def _test_url(url_name):
    """
    Generate test_url test for specified URL name.
    :param url_name: Name of URL to test
    :return: Test method
    """

    def test_admin(self):
        """
        Test the admin changelist pages.
        :param UrlsTestCase self: UrlsTestCase instance.
        """
        url = reverse(url_name)

        response = self.client.get(url)

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200, 'GET {url:}'.format(url=url))

    return test_admin


# Optimize test speed by using simple password hashing and disabling the debug toolbar.
@override_settings(AUTHENTICATION_BACKENDS=('django.contrib.auth.backends.ModelBackend',),
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@modify_settings(MIDDLEWARE_CLASSES={'remove': ('debug_toolbar.middleware.DebugToolbarMiddleware',)})
class UrlsTestCase(testcases.TestCase):
    """
    Test for pages.
    """
    longMessage = True

    url_names = []

    @classmethod
    def generateMethods(cls):
        """
        Dynamically generate test methods for each Admin instance.
        """
        # NOTE: Uses Django private API admin.site._registry
        for url_name in cls.url_names:
            test_url = _test_url(url_name)
            test_url.__name__ = str('test_url_{}'.format(url_name.replace('.', '_')))
            setattr(cls, test_url.__name__, test_url)

    @classmethod
    def setUpTestData(cls):
        super(UrlsTestCase, cls).setUpTestData()

        # Create superuser account to login
        user = User(username='superuser', is_staff=True, is_superuser=True)
        user.set_password('superuser')
        user.save()

        # Create profile
        Profile(user=user).save()

        # Create person
        person = Person(first_name='Super', last_name='User', gender=Person.GenderTypes.MAN, user=user, account_name=user.username)
        person.save()

        # Create membership type
        membership_type = MembershipType(name_nl='Test membership', price=13.37)
        membership_type.save()

        # Create membership
        Membership(member=person, type=membership_type, year=current_association_year()).save()

        # Create committee
        committee = Committee(name='Committee 1', abbreviation='Com1')
        committee.save()

        # Create function
        Function(person=person, committee=committee, function='Tester', begin=timezone.now()).save()

    def setUp(self):
        super(UrlsTestCase, self).setUp()

        # Every test needs a client.
        self.client = Client()

        # Login
        self.assertTrue(self.client.login(username='superuser', password='superuser'), 'login')

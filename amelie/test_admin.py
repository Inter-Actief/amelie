from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from django.test.testcases import TestCase
from django.test.utils import override_settings, modify_settings


def _test_admin(app_label, model_name):
    """
    Generate test_admin test for specified app and model.
    :param app_label: App label
    :param model_name: Model name
    :return: Test method
    """

    def test_admin(self):
        """
        Test the admin changelist pages.
        :param self: AdminTest instance.
        """
        url = reverse('admin:{app_label}_{model_name}_changelist'.format(app_label=app_label,
                                                                         model_name=model_name))

        response = self.client.get(url)

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200, 'GET {url:}'.format(url=url))

    return test_admin


def _test_admin_search(app_label, model_name):
    """
    Generate test_admin_search test for specified app and model.
    :param app_label: App label
    :param model_name: Model name
    :return: Test method
    """

    def test_admin_search(self):
        """
        Test the admin changelist pages using a search query.
        :param self: AdminTest instance.
        """
        url = reverse('admin:{app_label}_{model_name}_changelist'.format(app_label=app_label,
                                                                         model_name=model_name))

        # Add search query to url
        url = '{}?q=test'.format(url)

        response = self.client.get(url)

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200, 'GET {url:}'.format(url=url))

    return test_admin_search


# Optimize test speed by using simple password hashing and disabling the debug toolbar.
@override_settings(AUTHENTICATION_BACKENDS=('django.contrib.auth.backends.ModelBackend',),
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@modify_settings(MIDDLEWARE_CLASSES={'remove': ('debug_toolbar.middleware.DebugToolbarMiddleware',)})
class AdminTest(TestCase):
    """
    Test for admin pages.
    """
    longMessage = True

    @classmethod
    def generateMethods(cls):
        """
        Dynamically generate test methods for each Admin instance.
        """
        # NOTE: Uses Django private API admin.site._registry
        for model, admin_instance in admin.site._registry.items():
            app_label = model._meta.app_label
            model_name = model._meta.model_name

            test_admin = _test_admin(app_label, model_name)
            test_admin.__name__ = str('test_admin_{}_{}'.format(app_label, model_name))
            setattr(cls, test_admin.__name__, test_admin)

            test_admin_search = _test_admin_search(app_label, model_name)
            test_admin_search.__name__ = str('test_admin_search_{}_{}'.format(app_label, model_name))
            setattr(cls, test_admin_search.__name__, test_admin_search)

    @classmethod
    def setUpTestData(cls):
        super(AdminTest, cls).setUpTestData()

        # Create superuser account to login
        user = User(username='superuser', is_staff=True, is_superuser=True)
        user.set_password('superuser')
        user.save()

    def setUp(self):
        super(AdminTest, self).setUp()

        # Every test needs a client.
        self.client = Client()

        # Login
        self.assertTrue(self.client.login(username='superuser', password='superuser'), 'login')


AdminTest.generateMethods()

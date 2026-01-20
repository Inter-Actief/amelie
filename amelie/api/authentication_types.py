from abc import ABCMeta, abstractmethod

from oauth2_provider.models import AccessToken
from oauth2_provider.oauth2_backends import OAuthLibCore
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2 import Server


class Authentication(object):
    __metaclass__ = ABCMeta

    """Returns True if and only if this person is allowed to do an action

    Arguments:
        scopes: the scopes a person should have to perform this action
    """
    @abstractmethod
    def can(self, scopes):
        pass

    """Returns the person that is represented by this authentication"""
    @abstractmethod
    def represents(self):
        pass

    """Returns the application this authentication belongs to"""
    def get_application(self):
        return None


class AnonymousAuthentication(Authentication):
    def __init__(self, request):
        self.request = request

    def can(self, scopes):
        return False

    def represents(self):
        return None

    def __str__(self):
        return "AnonymousAuthentication"


class PersonBasedAuthentication(Authentication):
    def __init__(self, request):
        self.request = request

    def can(self, scopes):
        return True

    def represents(self):
        return self.request.user.person if hasattr(self.request.user, 'person') else None

    def __str__(self):
        return "PersonBasedAuthentication for {}".format(self.represents())


class OauthBasedAuthentication(Authentication):
    def __init__(self, request):
        self.request = request

    def can(self, scopes):
        validator = OAuth2Validator()
        core = OAuthLibCore(Server(validator))

        valid, oauthlib_req = core.verify_request(self.request, scopes=scopes.split())
        return valid

    def represents(self):
        return self.request.user.person if hasattr(self.request.user, 'person') else None

    def get_application(self):
        token = self.request.META.get('HTTP_AUTHORIZATION', 'Bearer ')
        token = token[7:]

        try:
            access_type = AccessToken.objects.get(token=token)

            return access_type.application
        except AccessToken.DoesNotExist:
            return None

    def __str__(self):
        return "OauthBasedAuthetication for {}".format(self.represents())


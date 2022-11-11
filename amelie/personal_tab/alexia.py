import datetime
import json
import requests

from django.conf import settings
from django.utils import timezone


def get_alexia():
    """
    Gets a working, logged in connection to Alexia.
    :return: A logged in connection to alexia
    :rtype: AlexiaInterface
    """
    alexia = AlexiaInterface()
    proxy = AlexiaProxy(alexia)

    # Authenticate with alexia
    res = proxy.login(username=alexia.api_user, password=alexia.api_pass)

    if res:
        # Authenticate for Inter-Actief organisation
        res = proxy.organization.current.set(organization=alexia.api_organization)

        if res:
            return proxy
        else:
            raise AlexiaConnectionError("Could not authenticate you for the organisation {}. Please check the "
                                        "organisation name and your permissions.".format(alexia.api_organization))
    else:
        raise AlexiaConnectionError("Could not login to the Alexia API. "
                                    "If Alexia is working properly, please check your username and password.")


def parse_datetime(datetimestr):
    """
    Convert datetime format 2014-09-24T13:39:56+00:00 to datetime object.

    Only accepts +00:00 timezone.
    """

    # Assume UTC date
    if datetimestr[-6:] != '+00:00':
        raise ValueError('Datetime "%s" is not in UTC' % datetimestr)

    return datetime.datetime.strptime(datetimestr[:-6], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


class AlexiaConnectionError(ConnectionError):
    pass


class AlexiaCallError(Exception):
    pass


class AlexiaInterface:
    """
    Interface to the Alexia API
    k.alberts
    """

    def __init__(self):
        """
        Get an interface to the Alexia API, which is not authenticated yet.
        """
        self.api_url = settings.ALEXIA_API['URL']
        self.api_user = settings.ALEXIA_API['USER']
        self.api_pass = settings.ALEXIA_API['PASSWORD']
        self.api_organization = settings.ALEXIA_API['ORGANIZATION']
        self.session = requests.Session()

    def call_method(self, method, params):
        """
        Calls a method of the Alexia API
        :param method: The name of the method to call
        :type method: str
        :param params: A dict of arguments to give to the method
        :type params: dict
        :return: result of the function call
        :rtype: dict
        """
        headers = {'content-type': 'application/json'}
        payload = {
            'method': method,
            'params': params,
            'jsonrpc': '2.0',
            'id': 0
        }

        return self.session.post(self.api_url, data=json.dumps(payload), headers=headers).json()


class AlexiaProxy:
    def __init__(self, interface, name=""):
        self._name = name
        self._interface = interface

    def __getattr__(self, item):
        if self._name:
            name = '{}.{}'.format(self._name, item)
        else:
            name = item
        return AlexiaProxy(self._interface, name)

    def __call__(self, *args, **kwargs):
        if args and not kwargs:
            param = args
        elif not args and kwargs:
            param = kwargs
        elif not args and not kwargs:
            param = {}
        else:
            raise ValueError("You may not combine args and kwargs for API calls.")

        response = self._interface.call_method(self._name, param)
        if 'result' in response:
            return response['result']
        else:
            error = response['error']
            raise AlexiaCallError("Error while calling function {}, Error code {}, message {}".format(self._name, error['code'], error['message']))

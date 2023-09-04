from typing import Union, List, Dict

from django.utils.translation import gettext
from oauth2_provider.models import AccessToken

from amelie.api.decorators import authentication_optional, authentication_required
from amelie.api.exceptions import NotLoggedInError

from modernrpc.core import rpc_method, REQUEST_KEY


@rpc_method(name='checkAuthToken')
@authentication_optional()
def check_auth_token(**kwargs) -> bool:
    """
    Checks if an auth token is still valid. It is recommended to do this after resuming your app,
    to see if the token was revoked.

    **Module**: `authentication`

    **Authentication**: _(none)_

    **Parameters**: _(none)_

    **Return**:
      `bool`: `true` if the token was valid and a user is attached, `false` otherwise.

    **Example**:

        --> {"method":"checkAuthToken", "params":[]}
        <-- {"result": true}
    """
    return kwargs.get('authentication', None) is not None


@rpc_method(name='revokeAuthToken')
def revoke_auth_token(**kwargs) -> bool:
    """
    Revokes an authentication token.

    **Module**: `authentication`

    **Authentication**: _(none)_

    **Parameters**: _(none)_

    **Return**:
      `bool`: `true` if the token was successfully revoked, `null` otherwise.

    **Raises:**

      NotLoggedInError: There was no authentication token to revoke.

    **Example**:

        --> {"method":"revokeAuthToken", "params":[]}
        <-- {"result": true}
    """
    try:
        token = kwargs.get(REQUEST_KEY).META.get('HTTP_AUTHORIZATION', 'Bearer ')
        token = token[7:]

        access_token = AccessToken.objects.get(token=token)
    except AccessToken.DoesNotExist:
        raise NotLoggedInError()

    access_token.delete()
    return True


@rpc_method(name='getAuthenticatedApps')
@authentication_required("account")
def get_authenticated_apps(**kwargs) -> Union[List[Dict], None]:
    """
    Retrieves the list of authenticated apps for the currently authenticated person.

    **Module**: `authentication`

    **Authentication**: REQUIRED (Scope: account)

    **Parameters**: _(none)_

    **Return**:
      `Union[List[Dict], None]`: An array of dictionaries containing information about the applications.

      Each returned element in the list has the following fields:

        - applicationId: The identifier of the application
        - applicationName: The name of the application
        - expires: The expiration date and time for the token associated with the application (RFC3339)
        - scopes: A dictionary of permitted scopes for the application, which MAY include any of the following fields:
            - education: Description of the education authentication scope
            - transaction: Description of the transaction authentication scope
            - account: Description of the account authentication scope
            - signup: Description of the signup authentication scope

    **Raises**:
      NotLoggedInError: Token was not recognized or already revoked.

    **Example**:

        --> {"method":"getAutenticatedApps", "params":[]}
        <-- {"result": [{
               "applicationId": 1,
               "applicationName": "Legacy getAuthToken API token",
               "expires": "2016-10-26T00:56:14+00:00",
               "scopes": {
                 "account": "De App krijgt toegang tot je naam, geboortedatum, studentnummer, machtigingstatus en commissiestatus",
                 "signup": "De App kan je in- en uitschrijven voor activiteiten"
               }
        }]}
    """
    person = kwargs.get('authentication').represents()

    if person is not None:
        result = []
        for access_token in person.user.oauth2_provider_accesstoken.order_by('-expires').all():
            translated_scopes = {}
            for s, d in access_token.scopes.items():
                translated_scopes[s] = gettext(d)

            result.append({
                "applicationName": access_token.application.name,
                "expires": access_token.expires.isoformat(),
                "scopes": translated_scopes,
                "applicationId": access_token.application.id
            })
        return result
    else:
        return None


from typing import Union, List, Dict

from modernrpc import RpcRequestContext
from oauth2_provider.models import AccessToken

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from amelie.api.api import api_server
from amelie.api.authentication_types import AnonymousAuthentication
from amelie.api.decorators import auth_optional, auth_required
from amelie.api.exceptions import NotLoggedInError


@api_server.register_procedure(name='checkAuthToken', auth=auth_optional, context_target='ctx')
def check_auth_token(ctx: RpcRequestContext = None, **kwargs) -> bool:
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
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)
    return is_authenticated


@api_server.register_procedure(name='revokeAuthToken', context_target='ctx')
def revoke_auth_token(ctx: RpcRequestContext = None, **kwargs) -> bool:
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
        token = ctx.request.META.get('HTTP_AUTHORIZATION', 'Bearer ')
        token = token[7:]

        access_token = AccessToken.objects.get(token=token)
    except AccessToken.DoesNotExist:
        raise NotLoggedInError()

    access_token.delete()
    return True


@api_server.register_procedure(name='getAuthenticatedApps', auth=auth_required('account'), context_target='ctx')
def get_authenticated_apps(ctx: RpcRequestContext = None, **kwargs) -> Union[List[Dict], None]:
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
    authentication = ctx.auth_result
    person = authentication.represents()

    if person is not None:
        result = []
        for access_token in person.user.oauth2_provider_accesstoken.order_by('-expires').all():
            translated_scopes = {}
            for s, d in access_token.scopes.items():
                translated_scopes[s] = _(d)

            result.append({
                "applicationName": access_token.application.name,
                "expires": access_token.expires.isoformat(),
                "scopes": translated_scopes,
                "applicationId": access_token.application.id
            })
        return result
    else:
        return None

@require_GET
@ensure_csrf_cookie  # Ensures the CSRF cookie is set
def get_csrf_token(request):
    response = JsonResponse({"message": "CSRF cookie set"})
    response["X-CSRFToken"] = get_token(request)  # Send CSRF token in headers
    return response

import logging
from typing import Union

from django.http import HttpRequest
from oauth2_provider.backends import OAuth2Backend

from amelie.api.authentication_types import PersonBasedAuthentication, OauthBasedAuthentication, Authentication, \
    AnonymousAuthentication
from amelie.api.exceptions import NotLoggedInError, PermissionDeniedError

logger = logging.getLogger(__name__)


def get_authentication(request: HttpRequest) -> Authentication:
    """
    Returns an authentication object for the request.
    This will be a PersonBasedAuthentication or OauthBasedAuthentication if the request is authenticated,
    or an AnonymousAuthentication if the request is not authenticated.
    """

    """
    We need to check two places for authorization tokens
    1) The request `user` for cookie authentication
    2) The `HTTP_AUTHORIZATION` header of the request
    """

    # 1) cookie-based authentication
    if hasattr(request, 'person') and request.person:
        auth = PersonBasedAuthentication(request)
        logger.debug("Client authenticated using cookie-based authentication")
        return auth

    # 2) HTTP Authorization header authentication
    if request.META.get('HTTP_AUTHORIZATION', '').startswith('Bearer'):
        user = OAuth2Backend().authenticate(request=request)
        if user:
            request.user = request._cached_user = user
            auth = OauthBasedAuthentication(request)
            logger.debug("Client authenticated using HTTP Authorization header")
            return auth
        else:
            logger.debug("Client failed to authenticate using HTTP Authorization header")

    # 3) Not authenticated
    logger.debug("Client did not provide valid authentication details")
    return AnonymousAuthentication(request)


def auth_optional(request: HttpRequest) -> Authentication:
    """
    Returns an Authentication object for the request, which describes if and how the request is authenticated.

    Example usage:
    ```
    @api_server.register_procedure(name='someApiMethod', auth=auth_optional, context_target='ctx')
    def some_api_method(ctx: RpcRequestContext = None, **kwargs):
        authentication: Authentication = ctx.auth_result
        is_authenticated: bool = authentication and not isinstance(authentication, AnonymousAuthentication)
        person: Optional[Person] = authentication.represents()
    ```
    """
    return get_authentication(request)


def auth_required(permission: str = None):
    """
    Require an Authenticated user, optionally require that that user has a specific oAuth permission.

    Example usage:
    ```
    @api_server.register_procedure(name='someApiMethod', auth=auth_required('signup'), context_target='ctx')
    def some_api_method(ctx: RpcRequestContext = None, **kwargs):
        authentication: Authentication = ctx.auth_result
        is_authenticated: bool = authentication and not isinstance(authentication, AnonymousAuthentication)
        person: Optional[Person] = authentication.represents()
    ```
    """
    def inner_auth_required(request: HttpRequest) -> Union[Authentication, bool]:
        auth = get_authentication(request)
        if not auth:
            raise NotLoggedInError()
        elif permission is not None and not auth.can(permission):
            raise PermissionDeniedError()
        else:
            return auth

    return inner_auth_required

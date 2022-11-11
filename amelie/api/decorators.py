import logging

from oauth2_provider.backends import OAuth2Backend

from amelie.api.authentication_types import PersonBasedAuthentication, OauthBasedAuthentication
from amelie.api.exceptions import PermissionDeniedError, NotLoggedInError

logger = logging.getLogger(__name__)


def inject_authentication(view_method, args, kwargs):
    """Mutates args and kwargs and injects an authentication object into the arguments"""

    """
    We need to check two places for authorization tokens
    1) The request `user` for cookie authentication
    2) The `HTTP_AUTHORIZATION` header of the request
    """

    # Storage for the retrieved authentication
    auth = None

    # The request is the very first argument to any django function
    request = args[0]

    # 1) cookie-based authentication
    if hasattr(request, 'person') and request.person:
        auth = PersonBasedAuthentication(request)
        logger.debug("Client authenticated using cookie-based authentication")

    # 2) HTTP Authorization header authentication
    elif request.META.get('HTTP_AUTHORIZATION', '').startswith('Bearer'):
        user = OAuth2Backend().authenticate(request=request)
        if user:
            request.user = request._cached_user = user
            auth = OauthBasedAuthentication(request)
            logger.debug("Client authenticated using HTTP Authorization header")

    # 3) Not authenticated
    else:
        logger.debug("Client did not provide authentication details")

    # Override authentication parameter
    kwargs["authentication"] = auth

    # Return new set of args and kwargs
    return args, kwargs


def authentication_optional():
    """Injects a kwarg `authentication` that represents the user who called this method"""
    def _method_wrapper(view_method):
        def _arguments_wrapper(*args, **kwargs):
            (newargs, newkwargs) = inject_authentication(view_method, args, kwargs)

            return view_method(*newargs, **newkwargs)
        return _arguments_wrapper
    return _method_wrapper


def authentication_required(permission=None):
    """Injects a kwarg `authentication` (like authentication_optional), but also checks a permission"""
    def _method_wrapper(view_method):
        def _arguments_wrapper(*args, **kwargs):
            (newargs, newkwargs) = inject_authentication(view_method, args, kwargs)

            auth = newkwargs["authentication"]

            if not auth:
                raise NotLoggedInError()
            elif permission is not None and not auth.can(permission):
                raise PermissionDeniedError()
            else:
                return view_method(*newargs, **newkwargs)
        return _arguments_wrapper
    return _method_wrapper

from django.utils.translation import gettext
from jsonrpc import jsonrpc_method
from oauth2_provider.models import AccessToken

from amelie.api.decorators import authentication_optional, authentication_required
from amelie.api.exceptions import NotLoggedInError


@jsonrpc_method('checkAuthToken() -> Boolean', validate=True)
@authentication_optional()
def check_auth_token(request, authentication=None):
    return authentication is not None


@jsonrpc_method('revokeAuthToken() -> Boolean', validate=True)
def revoke_auth_token(request):
    try:
        token = request.META.get('HTTP_AUTHORIZATION', 'Bearer ')
        token = token[7:]

        access_token = AccessToken.objects.get(token=token)
    except AccessToken.DoesNotExist:
        raise NotLoggedInError()

    access_token.delete()
    return True


@jsonrpc_method('getAuthenticatedApps() -> Object', validate=True)
@authentication_required("account")
def get_authenticated_apps(request, authentication=None):
    person = authentication.represents()

    if person is not None:
        result = []
        for access_token in person.user.accesstoken_set.order_by('-expires').all():
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


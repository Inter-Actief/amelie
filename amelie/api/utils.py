import uuid

from jsonrpc.exceptions import InvalidParamsError
from oauth2_provider.backends import OAuth2Backend

from amelie.api.common import parse_datetime


def generate_token():
    return uuid.uuid4()


def has_valid_oauth_token(request):
    with_oauth = False

    if request.META.get('HTTP_AUTHORIZATION', '').startswith('Bearer'):
        user = OAuth2Backend().authenticate(request=request)
        if user:
            request.user = request._cached_user = user
            request.person = user.person
            request.is_board = request.person.is_board()
            with_oauth = True

    return with_oauth


def parse_datetime_parameter(date):
    try:
        return parse_datetime(date)
    except ValueError:
        raise InvalidParamsError("Dates should be formatted as ISO 8601 (yyyy-mm-ddThh:mm:ss+hhmm)")

from amelie.tools.user import get_user_by_username


def allow_none(info, **kwargs):
    return False


def get_username_from_jwt_payload(payload):
    username = payload.get('preferred_username', None)
    if username is None:
        from graphql_jwt.exceptions import JSONWebTokenError
        raise JSONWebTokenError("Invalid payload")
    return username


def get_user_from_jwt_username(username):
    return get_user_by_username(username)

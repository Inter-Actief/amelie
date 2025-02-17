from typing import Union

from django.contrib.auth.models import User, AnonymousUser
from graphql import GraphQLResolveInfo


def is_logged_in(user_or_info: Union[User, AnonymousUser, GraphQLResolveInfo]):
    if isinstance(user_or_info, GraphQLResolveInfo):
        user_or_info = user_or_info.context.user if hasattr(user_or_info.context, 'user') else None
    return user_or_info.is_authenticated


def is_board(user_or_info: Union[User, AnonymousUser, GraphQLResolveInfo]):
    if isinstance(user_or_info, GraphQLResolveInfo):
        user_or_info = user_or_info.context.user if hasattr(user_or_info.context, 'user') else None
    board = hasattr(user_or_info, 'person') and hasattr(user_or_info.person, 'is_board') and user_or_info.person.is_board
    superuser = hasattr(user_or_info, 'is_superuser') and user_or_info.is_superuser
    return board or superuser

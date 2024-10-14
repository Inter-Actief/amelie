from graphql import GraphQLError


def _get_attribute(obj, dotted_path):
    value = obj
    for key in dotted_path.split('.'):
        if isinstance(value, list):
            value = value[int(key)]
        elif isinstance(value, dict):
            value = value[key]
        else:
            value = getattr(value, key)
    return value


def allow_only_self_or_board(identity):
    def wrapper_allow_only_self_or_board(func):
        def wrapper_args_allow_only_self_or_board(self, info, *args, **kwargs):
            user = info.context.user
            is_board = hasattr(user, 'person') and hasattr(user.person, 'is_board') and user.person.is_board
            is_superuser = hasattr(user, 'is_superuser') and user.is_superuser
            if not is_board and not is_superuser and _get_attribute(info, identity) != self.id:
                raise GraphQLError("Access denied.")
            return func(self, info, *args, **kwargs)
        return wrapper_args_allow_only_self_or_board
    return wrapper_allow_only_self_or_board

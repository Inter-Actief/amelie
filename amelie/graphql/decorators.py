from graphql import GraphQLError

from graphql_jwt.decorators import user_passes_test, login_required
from graphql_jwt.exceptions import PermissionDenied


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


AUTHORIZATION_FIELD_TYPES = ["public_fields", "login_fields", "committee_fields", "board_fields", "private_fields"]

def is_board_or_www(user):
    is_board = hasattr(user, 'person') and hasattr(user.person, 'is_board') and user.person.is_board
    is_superuser = hasattr(user, 'is_superuser') and user.is_superuser
    return is_board or is_superuser

def committee_required(committees: list):
    return user_passes_test(lambda u:is_board_or_www(u) or (hasattr(u, 'person') and hasattr(u.person, 'is_in_committee') and any(u.person.is_in_committee(committee) for committee in committees)))

def board_required():
    return user_passes_test(lambda u: is_board_or_www(u))

def no_access():
    return user_passes_test(lambda u: False)

def check_authorization(cls):
    """
    Enforces authorization checks when this model is queried.

    There are multiple types of fields, each can be defined on the DjangoObjectType:

    * public_fields: Fields that are accessible for people within being signed in.
    * login_fields: Fields that are only accessible after being signed in.
    * committee_fields: Fields that are only accessible by members of a committee, WWW superusers, and board members.
      * allowed_committees: When committee fields are defined, acronyms of visible committees should be passed.
    * board_fields: Fields that are only accessible by WWW superusers and board members.
    * private_fields: Fields that cannot be queried through the GraphQL API.
    * exempt_fields: Fields that are exempt from these checks,
                     their resolvers should have their own authorization checking.

    An example class would be:
    ```python
    class FooType(DjangoObjectType):
        public_fields = ['id']
        login_fields = ['login']
        committee_fields = ['committee']
        allowed_committees = ['some-committee']
        board_fields = ['board']
        private_fields = ['private']
        exempt_fields = ['exempt']

        class Meta:
            model = Foo
            fields = ['id', 'login', 'committee', 'board', 'private', 'exempt']

        def resolve_exempt(obj: Foo, info):
            # Custom authorization checks
            return obj
    ```
    """
    # Make sure that at least one of the authorization fields is present.
    if not any(hasattr(cls, authorization_field) for authorization_field in AUTHORIZATION_FIELD_TYPES):
        raise ValueError(f"At least one authorization field type should be defined for a GraphQL type, choose from: {', '.join(AUTHORIZATION_FIELD_TYPES)}")

    public_fields = getattr(cls, "public_fields", [])
    login_fields = getattr(cls, "login_fields", [])
    committee_fields = getattr(cls, "committee_fields", [])
    board_fields = getattr(cls, "board_fields", [])
    private_fields = getattr(cls, "private_fields", [])
    exempt_fields = getattr(cls, "exempt_fields", [])

    allowed_committees = getattr(cls, "allowed_committees", [])

    # If there are committee fields defined, then the allowed committee list cannot be non-empty
    if len(committee_fields) > 0 and len(allowed_committees) == 0:
        raise ValueError(f"The following fields are only visible by a committee: \"{','.join(committee_fields)}\", but there are no committees defined that can view this field. Make sure that \"allowed_committees\" has at least a single entry.")

    # Make sure that all the fields in the authorization fields are mutually exclusive.
    authorization_fields = [*public_fields, *login_fields, *committee_fields, *board_fields, *private_fields, *exempt_fields]
    if len(authorization_fields) != len(set(authorization_fields)):
        raise ValueError("Some of the authorization fields have overlapping Django fields. Make sure that they are all mutually exclusive!")

    # Make sure that all the fields that are defined in the fields list are in the authorization fields.
    if not all((missing_field := field) in authorization_fields for field in cls._meta.fields):
        raise ValueError(f"The field \"{missing_field}\" is defined in the Django fields list, but not in an authorization field list. All the django fields must be present in the authorization fields.")

    # Require a user to be signed in.
    for login_field in login_fields:
        setattr(cls, f"resolve_{login_field}", login_required(lambda self, info, field=login_field: getattr(self, login_field)))

    # Require a user to be in a committee
    for committee_field in committee_fields:
        setattr(cls, f"resolve_{committee_field}", committee_required(allowed_committees)(lambda self, info, field=committee_field: getattr(self, committee_field)))

    # Require a user to be in the board
    for board_field in board_fields:
        setattr(cls, f"resolve_{board_field}", board_required()(lambda self, info, field=board_field: getattr(self, board_field)))

    # No-one can access these fields
    for private_field in private_fields:
        setattr(cls, f"resolve_{private_field}", no_access()(lambda self, info, field: False))

    return cls

from graphql import GraphQLError

from graphql_jwt.decorators import user_passes_test, login_required

from amelie.graphql.helpers import is_board


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


AUTHORIZATION_FIELD_TYPES = ["public_fields", "login_fields", "committee_fields",
                             "board_fields", "private_fields", "manual_fields"]


def committee_required(committees: list):
    return user_passes_test(lambda u: is_board(u) or (hasattr(u, 'person') and hasattr(u.person, 'is_in_committee') and any(u.person.is_in_committee(committee) for committee in committees)))

def board_required():
    return user_passes_test(lambda u: is_board(u))

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
    * manual_fields: Fields for which the checks are manually managed,
                     these fields should have a custom resolver that has its own authorization checking.

    An example class would be:
    ```python
    @check_authorization
    class FooType(DjangoObjectType):
        public_fields = ['id']
        login_fields = ['login']
        committee_fields = ['committee']
        allowed_committees = ['some-committee']
        board_fields = ['board']
        private_fields = ['private']
        manual_fields = ['manual']

        class Meta:
            model = Foo
            fields = ['id', 'login', 'committee', 'board', 'private', 'exempt']

        def resolve_manual(obj: Foo, info):
            # Custom authorization checks
            return obj
    ```
    """
    # Make sure that at least one of the authorization fields is present.
    if not any(hasattr(cls, authorization_field) for authorization_field in AUTHORIZATION_FIELD_TYPES):
        raise ValueError(f"At least one authorization field type should be defined for GraphQL type \"{cls.__name__}\", choose from: {', '.join(AUTHORIZATION_FIELD_TYPES)}")

    public_fields = getattr(cls, "public_fields", [])
    login_fields = getattr(cls, "login_fields", [])
    committee_fields = getattr(cls, "committee_fields", [])
    board_fields = getattr(cls, "board_fields", [])
    private_fields = getattr(cls, "private_fields", [])
    manual_fields = getattr(cls, "manual_fields", [])

    allowed_committees = getattr(cls, "allowed_committees", [])

    # If there are committee fields defined, then the allowed committee list cannot be non-empty
    if len(committee_fields) > 0 and len(allowed_committees) == 0:
        raise ValueError(f"The following fields of \"{cls.__name__}\" are only visible by a committee: \"{','.join(committee_fields)}\", but there are no committees defined that can view this field. Make sure that \"allowed_committees\" has at least a single entry.")

    # Make sure that all the fields in the authorization fields are mutually exclusive.
    authorization_fields = [*public_fields, *login_fields, *committee_fields, *board_fields, *private_fields, *manual_fields]
    if len(authorization_fields) != len(set(authorization_fields)):
        raise ValueError("Some of the authorization fields of \"{cls.__name__}\" have overlapping Django fields. Make sure that they are all mutually exclusive!")

    # Make sure that all the fields that are defined in the fields list are in the authorization fields.
    if not all((missing_field := field) in authorization_fields for field in cls._meta.fields):
        raise ValueError(f"The field \"{missing_field}\" is defined in the Django fields list of \"{cls.__name__}\", but not in an authorization field list. All the django fields must be present in the authorization fields.")

    # Make sure that all manual fields that are defined in the fields list have a custom resolver defined.
    for manual_field in manual_fields:
        if not hasattr(cls, f"resolve_{manual_field}"):
            raise ValueError(f"The field \"{manual_field}\" is defined in the manual_fields list of \"{cls.__name__}\", but it has no custom resolver defined. All the manual fields must have a custom resolver that manages their authentication checks.")

    # Helper method to generate a resolver function for a field
    def get_resolver_method(field_name):
        # If class has a custom resolver method, wrap that original resolver method
        if hasattr(cls, f"resolve_{field_name}"):
            # If the original resolver was already wrapped before, return the original method
            if hasattr(cls, f"_orig_resolve_{field_name}"):
                resolve_field = getattr(cls, f"_orig_resolve_{field_name}")
            # If not already wrapped, we still have the original resolver, save it and return that
            else:
                resolve_field = getattr(cls, f"resolve_{field_name}")
                setattr(cls, f"_orig_resolve_{field_name}", resolve_field)

        # Else, return a resolver method that just returns the attribute value
        else:
            resolve_field = lambda self, *args, **kwargs: getattr(self, field_name)
        return resolve_field

    # Require a user to be signed in.
    for login_field in login_fields:
        resolve_login_field = get_resolver_method(login_field)
        setattr(cls, f"resolve_{login_field}", login_required(resolve_login_field))

    # Require a user to be in a committee
    for committee_field in committee_fields:
        resolve_committee_field = get_resolver_method(committee_field)
        setattr(cls, f"resolve_{committee_field}", committee_required(allowed_committees)(resolve_committee_field))

    # Require a user to be in the board
    for board_field in board_fields:
        resolve_board_field = get_resolver_method(board_field)
        setattr(cls, f"resolve_{board_field}", board_required()(resolve_board_field))

    # No-one can access these fields. Don't even try to use the defined resolver because the field should be private.
    for private_field in private_fields:
        setattr(cls, f"resolve_{private_field}", no_access()(lambda self, info, field: False))

    return cls

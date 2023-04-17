from graphene import ObjectType, Boolean


# Source: https://github.com/instruct-br/graphene-django-pagination
class PageInfoExtra(ObjectType):
    has_next_page = Boolean(
        required=True,
        name="hasNextPage",
        description="When paginating forwards, are there more items?",
    )
    has_previous_page = Boolean(
        required=True,
        name="hasPreviousPage",
        description="When paginating backwards, are there more items?",
    )

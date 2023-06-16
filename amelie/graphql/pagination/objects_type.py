from graphene import ObjectType, Boolean, Int


# Based on: https://github.com/instruct-br/graphene-django-pagination
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
    page = Int(
        required=True,
        name="page",
        description="Current page number"
    )
    num_pages = Int(
        required=True,
        name="numPages",
        description="Total page count"
    )
    limit = Int(
        required=False,
        name="limit",
        description="Limit as given to query"
    )
    offset = Int(
        required=True,
        name="offset",
        description="Offset as given to query"
    )

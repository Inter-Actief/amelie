import re

from collections import OrderedDict

from graphene import Connection, List, NonNull, Field
from graphene.relay.connection import ConnectionOptions

from amelie.graphql.pagination.objects_type import PageInfoExtra


# Source: https://github.com/instruct-br/graphene-django-pagination
class PaginationConnection(Connection):
    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, node=None, name=None, **options):
        _meta = ConnectionOptions(cls)
        base_name = re.sub("Connection$", "", name or cls.__name__) or node._meta.name # noqa

        if not name:
            name = "{}Connection".format(base_name)

        options["name"] = name
        _meta.node = node
        _meta.fields = OrderedDict(
            [
                (
                    "page_info",
                    Field(
                        PageInfoExtra,
                        name="pageInfo",
                        required=True,
                        description="Pagination data for this connection.",
                    ),
                ),
                (
                    "results",
                    Field(
                        NonNull(List(node)),
                        description="Contains the nodes in this connection.",
                    ),
                ),
            ]
        )

        return super(Connection, cls).__init_subclass_with_meta__(
            _meta=_meta, **options
        )

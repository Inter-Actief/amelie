from typing import List

from modernrpc import Protocol
from modernrpc.server import RpcServer

from django.views.generic import TemplateView


API_VERSION = 1.3

api_server = RpcServer(
    supported_protocol=Protocol.JSON_RPC,
    redirect_get_request_to="api:jsonrpc_docs"
)


@api_server.register_procedure
def version() -> str:
    """Returns the current API version.

    The client will then be able to determine which methods it can use and
    which methods it cannot use.

    A client can expect to have no issues if the client uses the same API
    version. In other cases, this API does not guarantee anything.
    """
    return str(API_VERSION)


@api_server.register_procedure
def methods(**kwargs) -> List[str]:
    """Introspect the API and return all callable methods.

    Returns an array with the methods.
    """
    return sorted(api_server.procedures.keys())


class ApiDocsView(TemplateView):
    template_name = "api/doc_index.html"

    def get_context_data(self, **kwargs):
        """Update context data with list of RPC methods of the current entry point.
        Will be used to display methods documentation page"""
        kwargs.setdefault("methods", sorted(api_server.procedures.values(), key=lambda m: m.name))
        return super().get_context_data(**kwargs)

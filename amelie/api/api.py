from typing import List

from modernrpc.core import rpc_method, registry, ENTRY_POINT_KEY, PROTOCOL_KEY

API_VERSION = 1.3


@rpc_method
def version() -> str:
    """Returns the current API version.

    The client will then be able to determine which methods it can use and
    which methods it cannot use.

    A client can expect to have no issues if the client uses the same API
    version. In other cases, this API does not guarantee anything.
    """
    return str(API_VERSION)


@rpc_method
def methods(**kwargs) -> List[str]:
    """Introspect the API and return all callable methods.

    Returns an array with the methods.
    """
    entry_point = kwargs.get(ENTRY_POINT_KEY)
    protocol = kwargs.get(PROTOCOL_KEY)

    return registry.get_all_method_names(entry_point, protocol, sort_methods=True)

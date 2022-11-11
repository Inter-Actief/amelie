from jsonrpc import jsonrpc_method
from jsonrpc.site import jsonrpc_site

API_VERSION = 1.3


@jsonrpc_method('version() -> String', validate=True)
def version(request):
    """Returns the current API version.

    The client will then be able to determine which methods it can use and
    which methods it cannot use.

    A client can expect to have no issues if the client uses the same API
    version. In other cases, this API does not guarantee anything.
    """

    return str(API_VERSION)


@jsonrpc_method('methods() -> Array', validate=True)
def methods(request):
    """Introspect the API and return all callable methods.

    Returns an array with the methods.
    """

    result = []

    for proc in jsonrpc_site.describe(request)['procs']:
        result.append(proc['name'])

    return result


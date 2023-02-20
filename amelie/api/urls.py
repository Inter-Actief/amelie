from django.urls import path

from modernrpc.core import Protocol
from modernrpc.views import RPCEntryPoint

app_name = 'api'


urlpatterns = [
    path('', RPCEntryPoint.as_view(protocol=Protocol.JSON_RPC), name="jsonrpc_mountpoint"),
    path('docs/', RPCEntryPoint.as_view(enable_doc=True, enable_rpc=False, template_name="api/doc_index.html")),
]

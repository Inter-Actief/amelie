from django.urls import path

from modernrpc.core import Protocol
from modernrpc.views import RPCEntryPoint

from amelie.companies.views import vivatbanner_get

app_name = 'api'


urlpatterns = [
    path('', RPCEntryPoint.as_view(protocol=Protocol.JSON_RPC), name="jsonrpc_mountpoint"),
    path('docs/', RPCEntryPoint.as_view(enable_doc=True, enable_rpc=False, template_name="api/doc_index.html")),
    path('vivat_banners/', vivatbanner_get, name='vivatbanner_get'),
]

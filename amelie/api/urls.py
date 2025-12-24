from django.urls import path

from amelie.companies.views import vivatbanner_get
from amelie.api.api import api_server, ApiDocsView
from amelie.api.authentication import get_csrf_token

app_name = 'api'


urlpatterns = [
    path('', api_server.view, name="jsonrpc_mountpoint"),
    path('docs/', ApiDocsView.as_view(), name="jsonrpc_docs"),
    path('vivat_banners/', vivatbanner_get, name='vivatbanner_get'),
	path('csrf-token/', get_csrf_token, name='get_csrf_token'),
]

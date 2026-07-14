from django.urls import path

from amelie.api.api import api_server, ApiDocsView
from amelie.api.authentication import get_csrf_token
from amelie.companies.views import vivatbanner_get
from amelie.members.views import AlexiaAgeCheckAPI, MinecraftWhitelistAPI
from amelie.tools.views import DocumensoWebhookView

app_name = 'api'


urlpatterns = [
    path('', api_server.view, name="jsonrpc_mountpoint"),
    path('docs/', ApiDocsView.as_view(), name="jsonrpc_docs"),
    path('csrf-token/', get_csrf_token, name='get_csrf_token'),

    # Separate (smaller) API endpoints used by various external systems.
    path('vivat_banners/', vivatbanner_get, name='vivatbanner_get'),
    path('alexia_age_check/', AlexiaAgeCheckAPI.as_view(), name='alexia_age_check_api'),
    path('minecraft_whitelist/', MinecraftWhitelistAPI.as_view(), name='minecraft_whitelist_api'),
    path('documenso_webhook/', DocumensoWebhookView.as_view(), name='documenso_webhook_api'),
]

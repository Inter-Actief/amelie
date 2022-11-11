from django.urls import path

from jsonrpc.site import jsonrpc_site

# Load all JSON-RPC methods
# noinspection PyUnresolvedReferences
from amelie.api import api, authentication, news, activitystream, committee, company, authentication, push,\
    narrowcasting, personal_tab, person, education, videos


app_name = 'api'


urlpatterns = [
    path('', jsonrpc_site.dispatch, name="jsonrpc_mountpoint"),
]

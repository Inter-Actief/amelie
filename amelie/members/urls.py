from django.conf.urls import include
from django.urls import path


app_name = 'members'

urlpatterns = [
    # Old (dutch) URLs to not break permalinks, placed first to let the URL names stick with the new URLs
    path('commissies/', include('amelie.members.committee_urls')),
    path('leden/', include('amelie.members.members_urls')),


    path('committees/', include('amelie.members.committee_urls')),
    path('members/', include('amelie.members.members_urls')),
]

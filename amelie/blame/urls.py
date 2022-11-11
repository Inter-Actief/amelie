from django.urls import path

from amelie.blame.views import BlameOverview, BlameModelOverview, BlameObjectChangelog, BlameObjectDetail

app_name = 'blame'

urlpatterns = [
    path('', BlameOverview.as_view(), name="overview"),
    path('<int:content_type>/', BlameModelOverview.as_view(), name="model_overview"),
    path('<int:content_type>/<int:object_pk>/', BlameObjectChangelog.as_view(), name="object_changelog"),
    path('detail/<int:pk>/', BlameObjectDetail.as_view(), name="object_detail"),
]

# vim:set sw=4 sts=4 ts=4 et si:

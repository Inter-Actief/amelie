from django.urls import path

from amelie.claudia.kanidm_views import KanidmHome, \
    KanidmPersonList, KanidmPersonDetail, \
    KanidmGroupList, KanidmGroupDetail, \
    KanidmServiceAccountList, KanidmServiceAccountDetail

"""
The urls in this file are included in the amelie/claudia/claudia_urls.py
"""


urlpatterns = [
    path('', KanidmHome.as_view(), name="kanidm_home"),

    path('persons/', KanidmPersonList.as_view(), name="kanidm_person_list"),
    path('persons/<str:uuid>/', KanidmPersonDetail.as_view(), name="kanidm_person_detail"),

    path('groups/', KanidmGroupList.as_view(), name="kanidm_group_list"),
    path('groups/<str:uuid>/', KanidmGroupDetail.as_view(), name="kanidm_group_detail"),

    path('service_accounts/', KanidmServiceAccountList.as_view(), name="kanidm_service_account_list"),
    path('service_accounts/<str:uuid>/', KanidmServiceAccountDetail.as_view(), name="kanidm_service_account_detail"),
]

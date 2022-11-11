from django.urls import path
from amelie.claudia.claudia_views import MappingTimeline, TimelineList, SharedDriveList, SharedDriveAdd, \
    SharedDriveDetail, PersonalAliasView, PersonalAliasAddView, PersonalAliasRemoveView, PersonalAliasListView
from amelie.claudia.claudia_views import ClaudiaHome, MappingList, MappingDetailView, AddToMappingView, \
    AddToMappingList, AddMappingToList, MappingFind, MappingVerify
from amelie.claudia.claudia_views import ExtraGroupList, ExtraGroupAdd, ExtraGroupDetail
from amelie.claudia.claudia_views import ExtraPersonList, ExtraPersonAdd, ExtraPersonDetail
from amelie.claudia.claudia_views import AliasGroupList, AliasGroupAdd, AliasGroupDetail
from amelie.claudia.claudia_views import ContactList, ContactAdd, ContactDetail
from amelie.claudia.claudia_views import LinkDelete, EmailDetail

"""
The urls in this file are included in the amelie/urls.py, which gives the names
of the urls in this file a prefix of 'claudia-'
"""


app_name = 'claudia'

urlpatterns = [
    path('', ClaudiaHome.as_view(), name="home"),

    path('mapping/', MappingList.as_view(), name="mapping_list"),
    path('mapping/<int:pk>/', MappingDetailView.as_view(), name="mapping_view"),
    path('mapping/<int:pk>/add/', AddToMappingList.as_view(), name='add_to_mapping'),
    path('mapping/<int:pk>/add-to/', AddMappingToList.as_view(), name="add_mapping_to"),
    path('mapping/<int:pk>/add/<int:member_id>/', AddToMappingView.as_view(),
         name="mapping_add_mapping"),
    path('mapping/<int:pk>/verify/', MappingVerify.as_view(), name="mapping_verify"),
    path('mapping/<int:pk>/timeline/', MappingTimeline.as_view(), name='mapping_timeline'),
    path('mapping/<str:obj_type>/<int:ident>/', MappingFind.as_view(),
         name="mapping_find"),

    path('mapping/<int:pk>/personal_alias/', PersonalAliasView.as_view(), name="personal_alias"),
    path('mapping/<int:pk>/personal_alias/add/', PersonalAliasAddView.as_view(), name="personal_alias_add"),
    path('mapping/personal_alias/remove/<int:pk>)/', PersonalAliasRemoveView.as_view(),
         name="personal_alias_remove"),
    path('personal_aliases/', PersonalAliasListView.as_view(), name="all_personal_aliases"),

    path('extragroup/', ExtraGroupList.as_view(), name='extragroup_list'),
    path('extragroup/new/', ExtraGroupAdd.as_view(), name='extragroup_add'),
    path('extragroup/<int:pk>/', ExtraGroupDetail.as_view(), name='extragroup_view'),

    path('shareddrive/', SharedDriveList.as_view(), name='shareddrive_list'),
    path('shareddrive/new/', SharedDriveAdd.as_view(), name='shareddrive_add'),
    path('shareddrive/<int:pk>/', SharedDriveDetail.as_view(), name='shareddrive_view'),

    path('extraperson/', ExtraPersonList.as_view(), name='extraperson_list'),
    path('extraperson/new/', ExtraPersonAdd.as_view(), name='extraperson_add'),
    path('extraperson/<int:pk>/', ExtraPersonDetail.as_view(), name='extraperson_view'),

    path('aliasgroup/', AliasGroupList.as_view(), name='aliasgroup_list'),
    path('aliasgroup/new/', AliasGroupAdd.as_view(), name='aliasgroup_add'),
    path('aliasgroup/<int:pk>/', AliasGroupDetail.as_view(), name='aliasgroup_view'),

    path('contact/', ContactList.as_view(), name='contact_list'),
    path('contact/new/', ContactAdd.as_view(), name='contact_add'),
    path('contact/<int:pk>/', ContactDetail.as_view(), name='contact_view'),

    path('delete/<int:link_id>/', LinkDelete.as_view(), name='link_delete'),

    path('email/<str:email>/', EmailDetail.as_view(), name='email_detail'),

    path('timeline/', TimelineList.as_view(), name='timeline_list'),
]

# vim:set sw=4 sts=4 ts=4 et si:

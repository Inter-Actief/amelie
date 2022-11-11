from django.urls import path
from django.views.generic import RedirectView

from amelie.companies import views


app_name = 'companies'

urlpatterns = [
    path('banners/', views.banner_list, name='banner_list'),
    path('banners/<int:id>/', views.banner_edit, name='banner_edit'),
    path('banners/create_web/', views.websitebanner_create, name='websitebanner_create'),
    path('banners/create_tv/', views.televisionbanner_create, name='televisionbanner_create'),

    path('activities/', views.event_list, name='event_list'),
    path('activities/<int:id>/', views.event_details, name='event_details'),
    path('activities/<int:id>/edit/', views.event_edit, name='event_edit'),
    path('activities/<int:id>/delete/', views.event_delete, name='event_delete'),
    path('activities/create/', views.event_create, name='event_create'),
    path('activities/old/', views.event_old, name='event_old'),

    path('activities/external_activities.ics', views.company_events_ics, name='events_ics'),
    path('activities/<int:id>/external_activity.ics', views.company_event_ics, name='event_ics'),

    path('', views.company_list, name='company_list'),
    path('overview/', views.company_overview, name='company_overview'),
    path('old/', views.company_old, name='company_old'),
    path('overview/old/', views.company_overview_old, name='company_overview_old'),
    path('create/', views.company_create, name='company_create'),
    path('statistics/', views.CompanyStatisticsView.as_view(), name='statistics'),
    path('<slug:slug>/', views.company_details, name='company_details'),
    path('<slug:slug>/edit/', views.company_edit, name='company_edit'),

    # Dutch redirect URLs
    path('activiteiten/<int:id>/', RedirectView.as_view(pattern_name='companies:event_details', permanent=True)),
    path('activiteiten/externe_activiteiten.ics', RedirectView.as_view(pattern_name='companies:events_ics', permanent=True)),
    path('activiteiten/<int:id>/externe_activiteit.ics', RedirectView.as_view(pattern_name='companies:event_ics', permanent=True)),
]

from django.urls import path
from django.views.generic.base import RedirectView

from amelie.education import views


app_name = 'education'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('news/', views.news_archive, name='news_archive'),

    path('complaints/', views.complaints, name='complaints'),
    path('complaints/<int:complaint_id>/', views.complaint, name='complaint'),
    path('complaints/<int:pk>/edit/', views.complaint_edit, name='complaint_edit'),
    path('complaints/new/', views.complaint_new, name='complaint_new'),
    path('complaints/course/new/', views.course_new, name='course_new'),
    path('complaints/module/new/', views.module_new, name='module_new'),

    path('bouquet/', views.educational_bouquet, name='bouquet'),
    # path('awards', views.dea_nomination, name='dea_nomination'),
    # path('awards/vote', views.dea_vote, name='dea_vote'),
    path('courses/<int:course_code>/<slug:slug>/', views.course, name='course'),
    path('modules/<int:course_code>/<slug:slug>/', views.ModuleView.as_view(), name='module'),

    # path('summaries/', views.summaries, name='summaries'),

    path('awards/', views.awards, name='awards'),

    path('category/new/', views.category_new, name='category_new'),
    path('category/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('category/<int:category_id>/delete/', views.category_delete, name='category_delete'),

    path('new/', views.page_new, name='page_new'),
    path('<int:page_id>/edit/', views.page_edit, name='page_edit'),
    path('<int:page_id>/delete/', views.page_delete, name='page_delete'),
    path('<int:page_id>/up/', views.page_up, name='page_up'),
    path('<int:page_id>/down/', views.page_down, name='page_down'),

    path('activities/', views.event_overview, name='event_overview'),
    path('activities/<int:event_id>/', views.event, name='event'),
    path('activities/edit/<int:event_id>/', views.event_edit, name='event_edit'),
    path('activities/delete/<int:event_id>/', views.event_delete, name='event_delete'),
    path('activities/new/', views.event_new, name='event_new'),

    # Dutch URLs for permalink compatibility
    path('nieuws/<str:path>', RedirectView.as_view(url='/news/%(path)s', permanent=True)),
    path('klachten/<str:path>', RedirectView.as_view(url='/complaints/%(path)s', permanent=True)),
    path('onderwijsbloemetje/<str:path>', RedirectView.as_view(url='/bouquet/%(path)s', permanent=True)),
    path('samenvattingen/<str:path>', RedirectView.as_view(url='/summaries/%(path)s', permanent=True)),
    path('activiteiten/<str:path>', RedirectView.as_view(url='/activities/%(path)s', permanent=True)),
]

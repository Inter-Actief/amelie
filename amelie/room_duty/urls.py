from django.urls import path
from django.views.generic import RedirectView

from amelie.room_duty import views


app_name = 'room_duty'

urlpatterns = [
    path('', views.index, name='index'),
    path('table/add/', views.table_add, name='table_add'),
    path('table/<int:pk>/change/',
        views.table_change, name='table_change'),
    path('table/<int:pk>/change/persons/',
        views.table_change_persons, name='table_change_persons'),
    path('table/<int:pk>/change/persons/<int:person_pk>/delete/',
        views.table_change_persons_delete, name='table_change_persons_delete'),
    path('table/<int:pk>/delete/',
        views.table_delete, name='table_delete'),
    path('table/<int:pk>/room_duty/add/',
        views.table_room_duty_add, name='table_room_duty_add'),
    path('table/<int:pk>/room_duty/<int:room_duty_pk>/',
        views.table_room_duty_delete, name='table_room_duty_delete'),
    path('table/<int:pk>/',
        views.table_overview, name='table_overview'),
    path('table/<int:pk>/fill/',
        views.table_fill, name='table_fill'),
    path('table/<int:pk>/print/',
        views.table_print, name='table_print'),

    path('balcony_duty/',
        views.balcony_duty, name='balcony_duty'),
    path('balcony_duty/<int:pk>/down/',
        views.balcony_duty_down, name='balcony_duty_down'),
    path('balcony_duty/<int:pk>/up/',
        views.balcony_duty_down, name='balcony_duty_up'),
    path('balcony_duty/<int:pk>/delete/',
        views.balcony_duty_delete, name='balcony_duty_delete'),

    path('pool/', views.pools, name='pools'),
    path('pool/add/', views.pool_add, name='pool_add'),
    path('pool/<int:pk>/delete/',
        views.pool_delete, name='pool_delete'),
    path('pool/<int:pk>/persons/',
        views.pool_change_persons, name='pool_change_persons'),
    path('pool/<int:pk>/persons/<int:person_id>/delete/',
        views.pool_delete_person, name='pool_delete_person'),
    path('template/', views.templates, name='templates'),
    path('template/add/', views.template_add, name='template_add'),

    path('template/<int:pk>/change/',
        views.template_change, name='template_change'),
    path('template/<int:pk>/delete/',
        views.template_delete, name='template_delete'),
    path('template/<int:pk>/room_duty/add/',
        views.template_room_duty_add, name='template_room_duty_add'),
    path('template/<int:pk>/room_duty/<int:room_duty_pk>/delete/',
        views.template_room_duty_delete, name='template_room_duty_delete'),

    path('kalender/<str:path>', RedirectView.as_view(url='/room_duty/calendar/%(path)s', permanent=True)),
    path('calendar/<int:pk>.ics', views.room_duty_ics, name='room_duty_ics'),
]

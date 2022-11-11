from django.urls import path

from amelie.publications import views


app_name = 'publications'

urlpatterns = [
    path('', views.PublicationList.as_view(), name='list_publications'),
    path('new/', views.PublicationCreate.as_view(), name='new_publication'),
]

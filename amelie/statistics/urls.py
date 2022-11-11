from django.urls import path

from amelie.statistics import views

app_name = 'statistics'

urlpatterns = [
    path('', views.statistics, name='statistics'),
    path('hits/', views.hits, name='hits'),
]

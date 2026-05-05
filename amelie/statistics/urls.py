from django.urls import path

from amelie.statistics import views

app_name = 'statistics'

urlpatterns = [
    path('', views.statistics, name='statistics'),
    path('<int:year>/', views.statistics_year, name='statistics_year'),
    path('hits/', views.hits, name='hits'),
]

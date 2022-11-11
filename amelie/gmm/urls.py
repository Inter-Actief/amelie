from django.urls import path

from amelie.gmm import views


app_name = 'gmm'

urlpatterns = [
    path('', views.index, name='index'),
]

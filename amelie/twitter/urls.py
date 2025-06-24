from django.urls import path

from amelie.twitter import views


app_name = 'twitter'

urlpatterns = [
    path('', views.index, name='index'),
]

from django.urls import re_path

from amelie.calendar import views

app_name = 'calendar'

urlpatterns = [
    re_path(r'^(?P<pk>\d+)/pay/', views.PayParticipationView.as_view(), name='pay_participation'),
]

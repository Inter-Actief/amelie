from django.conf.urls import url

from amelie.calendar import views

app_name = 'calendar'

urlpatterns = [
    url(r'^(?P<pk>\d+)/pay/', views.PayParticipationView.as_view(), name='pay_participation'),
]

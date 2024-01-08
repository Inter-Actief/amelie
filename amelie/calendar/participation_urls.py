from django.urls import path

from amelie.calendar import views

app_name = 'calendar'

urlpatterns = [
    path(r'<int:pk>/pay/', views.PayParticipationView.as_view(), name='pay_participation'),
]

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from amelie.graphql.views import IAGraphQLView

app_name = 'graphql'


urlpatterns = [
    path('', csrf_exempt(IAGraphQLView.as_view(graphiql=True)))
]

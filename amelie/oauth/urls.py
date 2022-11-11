from django.urls import path

from amelie.oauth.views import token_login, send_token, RequestOAuth

app_name = 'oauth'
urlpatterns = [
    path('token_login/<str:token>/', token_login, name="token_login"),
    path('send_token/<int:person_id>/', send_token, name="send_token"),
    path('request_access/', RequestOAuth.as_view(), name="request_oauth")
]

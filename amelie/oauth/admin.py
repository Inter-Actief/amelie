from django.contrib import admin

from amelie.oauth.models import LoginToken

admin.site.register(LoginToken)

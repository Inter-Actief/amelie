from django.contrib import admin

from amelie.api.models import PushNotification


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

from django.contrib import admin

from amelie.weekmail.models import WeekMail, WeekMailNewsArticle


class WeekMailAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'mailtype', 'published')


admin.site.register(WeekMail, WeekMailAdmin)
admin.site.register(WeekMailNewsArticle)

from django.contrib import admin

from amelie.about.models import Page


class PageAdmin(admin.ModelAdmin):
    list_display = ('name_nl', 'name_en')


admin.site.register(Page, PageAdmin)

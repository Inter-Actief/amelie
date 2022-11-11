from django.contrib import admin

from .models import Publication,PublicationType


class PublicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'publication_type', 'date_published', 'public')


admin.site.register(PublicationType)
admin.site.register(Publication, PublicationAdmin)

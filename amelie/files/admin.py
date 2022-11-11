from django.contrib import admin

from amelie.files.models import Attachment


class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file','mimetype','owner','public', 'file',)
    search_fields = ['owner__first_name', 'owner__last_name']
    list_filter = ('mimetype',)
    actions = ['make_public', 'make_protected']

    def make_public(self, request, queryset):
        queryset.update(public=True)
    make_public.short_description = "Maak geselecteerde foto's publiek beschikbaar"

    def make_protected(self, request, queryset):
        queryset.update(public=False)
    make_protected.short_description = "Maak geselecteerde foto's niet publiek beschikbaar"

admin.site.register(Attachment, AttachmentAdmin)

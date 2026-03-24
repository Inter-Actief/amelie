from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from amelie.files.models import Attachment, GMMDocument, File


class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'mimetype', 'owner', 'public')
    search_fields = ['owner__first_name', 'owner__last_name']
    list_filter = ('mimetype',)
    actions = ['make_public', 'make_protected']
    readonly_fields = ('thumb_small', 'thumb_medium', 'thumb_large', 'mimetype', 'owner', 'created', 'modified',
                       'thumb_small_height', 'thumb_small_width', 'thumb_medium_height', 'thumb_medium_width',
                       'thumb_large_height', 'thumb_large_width')

    def make_public(self, request, queryset):
        queryset.update(public=True)
    make_public.short_description = "Maak geselecteerde foto's publiek beschikbaar"

    def make_protected(self, request, queryset):
        queryset.update(public=False)
    make_protected.short_description = "Maak geselecteerde foto's niet publiek beschikbaar"


class GMMDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'gmm_link', 'caption', 'uploader', 'file')
    list_filter = ('gmm',)
    search_fields = ['uploader__first_name', 'uploader__last_name']

    def gmm_link(self, obj):
        if obj.gmm:
            link = reverse("admin:gmm_gmm_change", args=(obj.gmm.id, ))
            text = str(obj.gmm)
            return format_html(f"<a href='{link}'>{text}</a>")
        else:
            return "-"

    def has_add_permission(self, request):
        return request.user.is_superuser


class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'caption', 'uploader', 'file', 'created', 'modified')
    readonly_fields = ('uploader', 'created', 'modified')
    search_fields = ['uploader__first_name', 'uploader__last_name', 'caption']

    def save_model(self, request, obj, form, change):
        # Set the uploader before saving
        obj.uploader = request.user.person if hasattr(request.user, 'person') else None
        super().save_model(request, obj, form, change)


admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(GMMDocument, GMMDocumentAdmin)
admin.site.register(File, FileAdmin)

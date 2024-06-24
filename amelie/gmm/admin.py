from django.contrib import admin
from django.utils.translation import gettext as _

from amelie.files.models import GMMDocument
from amelie.gmm.models import GMM
from amelie.gmm.forms import GMMAdminForm


class GMMDocumentInlineAdmin(admin.TabularInline):
    model = GMMDocument
    extra = 0  # No extra empty fields, new uploads are handled via the separate button.
    max_num = 0  # No extra empty fields, new uploads are handled via the separate button.
    verbose_name = _("GMM Document")
    verbose_name_plural = _("GMM Documents")


class GMMAdmin(admin.ModelAdmin):
    form = GMMAdminForm
    inlines = [GMMDocumentInlineAdmin]
    list_display = ("date", "num_files")

    def num_files(self, obj):
        return str(len(obj.documents.all()))
    num_files.short_description = _("# documents")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_documents(
            gmm=form.instance,
            uploader=request.user.person if hasattr(request.user, 'person') else None
        )


admin.site.register(GMM, GMMAdmin)

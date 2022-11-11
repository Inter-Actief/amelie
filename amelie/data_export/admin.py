from django.contrib import admin

from amelie.data_export.models import DataExport, ApplicationStatus


class ReadOnlyTabularInline(admin.TabularInline):
    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ApplicationStatusInline(ReadOnlyTabularInline):
    model = ApplicationStatus

    readonly_fields = ['data_export', 'application', 'status']


class DataExportAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'request_timestamp', 'is_ready')
    search_fields = ('id', 'person__first_name', 'person__last_name')
    raw_id_fields = ('person',)
    readonly_fields = ('download_code', 'person', 'filename', 'request_timestamp', 'complete_timestamp',
                       'download_count', 'is_ready')

    inlines = [ApplicationStatusInline]

    fields = ('download_code', 'person', 'filename', 'request_timestamp', 'complete_timestamp', 'download_count',
              'is_ready')


admin.site.register(DataExport, DataExportAdmin)

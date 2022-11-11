from django.contrib import admin

from amelie.companies.models import Company, TelevisionBanner, WebsiteBanner


class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name_nl', 'name_en', 'start_date', 'end_date', 'show_in_app']


class WebsiteBannerAdmin(admin.ModelAdmin):
    ordering = ['id', 'name']
    list_display = ['name', 'start_date', 'end_date', 'active']


class TelevisionBannerAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'active']


admin.site.register(Company, CompanyAdmin)
admin.site.register(WebsiteBanner, WebsiteBannerAdmin)
admin.site.register(TelevisionBanner, TelevisionBannerAdmin)

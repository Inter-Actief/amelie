from django.contrib import admin

from amelie.tools.models import Profile


class AbbreviationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'abbreviation', 'type')
    search_fields = ('name', 'abbreviation')
    list_filter = ('type',)


class AbbreviationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'abbreviation')
    search_fields = ('name', 'abbreviation')


class DescriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description',)


class NameAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)
    search_fields = ('name',)


admin.site.register(Profile)

from django.contrib import admin

from amelie.claudia.models import Mapping, Event, ExtraGroup, \
    Membership, ExtraPerson, Timeline, AliasGroup, Contact, ExtraPersonalAlias, SharedDrive, DrivePermission


class ExtraPersonalAliasInline(admin.TabularInline):
    model = ExtraPersonalAlias


class MappingAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'type', 'ident', 'email', 'active', 'guid',)
    list_filter = ('type', 'active',)
    search_fields = ['name', 'email', ]
    inlines = [ExtraPersonalAliasInline]


class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email',)
    list_select_related = True
    search_fields = ('name', 'email',)


class AliasGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'email',)
    list_select_related = True
    search_fields = ('name', 'email',)


class EventAdmin(admin.ModelAdmin):
    date_hierarchy = 'execute'
    list_display = ('type', 'mapping', 'execute',)
    list_filter = ('type',)
    raw_id_fields = ('mapping',)
    search_fields = ('mapping__name',)


class ExtraGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'active', 'email', 'adname', 'dogroup',)
    list_filter = ('active', 'dogroup',)
    search_fields = ['name', 'email', 'adname', 'description', ]


class SharedDriveAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ['name', ]


class DrivePermissionAdmin(admin.ModelAdmin):
    list_display = ('drive', 'mapping',)
    list_filter = ('drive', 'mapping', )


class MembershipAdmin(admin.ModelAdmin):
    list_display = ('group', 'member', 'ad', 'mail',)
    list_filter = ('ad', 'mail',)
    raw_id_fields = ('group', 'member',)
    search_fields = ('group__name', 'member__name', 'description',)


class ExtraPersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'active', 'email', 'adname',)
    list_filter = ('active',)
    search_fields = ['name', 'email', 'adname', 'description', ]


class TimelineAdmin(admin.ModelAdmin):
    date_hierarchy = 'datetime'
    list_display = ('datetime', 'name', 'type', 'description',)
    list_filter = ('type',)
    raw_id_fields = ('mapping',)
    search_fields = ['name', 'mapping__name', 'description', ]


admin.site.register(Mapping, MappingAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.register(AliasGroup, AliasGroupAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(ExtraGroup, ExtraGroupAdmin)
admin.site.register(Membership, MembershipAdmin)
admin.site.register(ExtraPerson, ExtraPersonAdmin)
admin.site.register(Timeline, TimelineAdmin)
admin.site.register(SharedDrive, SharedDriveAdmin)
admin.site.register(DrivePermission, DrivePermissionAdmin)

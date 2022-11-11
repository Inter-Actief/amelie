from django.contrib import admin

from amelie.room_duty.models import *


class RoomDutyTableAdmin(admin.ModelAdmin):
    list_display = ('title', 'begin')


class RoomDutyAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'table', 'begin', 'end')


class RoomDutyAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_duty', 'person', 'availability')


admin.site.register(RoomDutyPool)
admin.site.register(RoomDutyTable, RoomDutyTableAdmin)
admin.site.register(RoomDuty, RoomDutyAdmin)
admin.site.register(RoomDutyTableTemplate)
admin.site.register(RoomDutyTemplate)
admin.site.register(RoomDutyAvailability, RoomDutyAvailabilityAdmin)
admin.site.register(BalconyDutyAssociation)

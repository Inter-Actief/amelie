from django.contrib import admin

from amelie.calendar.models import Event, Participation


class EventAdmin(admin.ModelAdmin):
    list_display = ('id',  'summary_nl', 'summary_en', 'organizer', 'location', 'begin', 'end', 'public',)
    search_fields = ('summary_nl', 'summary_en', 'description_nl', 'description_en',)
    date_hierarchy = 'begin'
    list_filter = ('public',)
    raw_id_fields = ('participants', 'attachments', )


class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('id',  'event', 'person', 'payment_method', 'added_on', 'added_by',)
    search_fields = ('event__summary_nl', 'event__summary_en', 'person__first_name', 'person__last_name',)
    date_hierarchy = 'added_on'
    list_filter = ('payment_method',)
    raw_id_fields = ('event', 'person', 'added_by', )


admin.site.register(Event, EventAdmin)
admin.site.register(Participation, ParticipationAdmin)

from django.contrib import admin

from amelie.activities.models import Activity, Restaurant, Dish, EventDeskRegistrationMessage, ActivityLabel


class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'summary_nl', 'summary_en', 'organizer', 'location', 'begin', 'end', 'public',)
    search_fields = ('summary_nl', 'summary_en', 'description_nl', 'description_en',)
    date_hierarchy = 'begin'
    list_filter = ('public',)
    raw_id_fields = ('participants', 'attachments', 'photos', 'components', )


class DishInline(admin.TabularInline):
    model = Dish


class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'available')
    inlines = (DishInline,)


class EventDeskRegistrationMessageAdmin(admin.ModelAdmin):
    list_display = ('message_date', 'activity', 'event_name')


admin.site.register(Activity, ActivityAdmin)
admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(EventDeskRegistrationMessage, EventDeskRegistrationMessageAdmin)
admin.site.register(ActivityLabel)

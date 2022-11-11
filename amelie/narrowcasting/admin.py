from django.contrib import admin

from amelie.narrowcasting.models import TelevisionPromotion, SpotifyAssociation


class TelevisionPromotionAdmin(admin.ModelAdmin):
    list_display = ('id', 'attachment', 'activity', 'start', 'end')


admin.site.register(TelevisionPromotion, TelevisionPromotionAdmin)
admin.site.register(SpotifyAssociation)

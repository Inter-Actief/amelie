from django.contrib import admin

from amelie.videos.models import YouTubeVideo, StreamingIAVideo


class YouTubeVideoAdmin(admin.ModelAdmin):
    list_display = ('video_id', 'title', 'public', 'publisher', 'date_published',)
    search_fields = ('title',)
    list_filter = ('public', 'publisher',)
    date_hierarchy = 'date_published'


class StreamingIAVideoAdmin(admin.ModelAdmin):
    list_display = ('video_id', 'title', 'public', 'publisher', 'date_published',)
    search_fields = ('title',)
    list_filter = ('public', 'publisher',)
    date_hierarchy = 'date_published'


admin.site.register(YouTubeVideo, YouTubeVideoAdmin)
admin.site.register(StreamingIAVideo, StreamingIAVideoAdmin)

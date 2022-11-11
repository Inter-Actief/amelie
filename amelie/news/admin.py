from django.contrib import admin

from amelie.news.models import NewsItem


class NewsAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_nl', 'title_en', 'introduction_nl', 'introduction_en', 'publisher','author','publication_date')
    search_fields = ('title_nl', 'title_en', 'introduction_nl', 'introduction_en', 'content_nl', 'content_en')
    date_hierarchy = 'publication_date'
    list_filter = ('publisher','author')
admin.site.register(NewsItem, NewsAdmin)

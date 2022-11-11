from django.contrib.syndication.views import Feed
from django.utils.translation import gettext_lazy as _

from amelie.news.models import NewsItem


class LatestNews(Feed):
    title = _('IA News')
    link = '/news/'
    description = _('The news by your favorite Study Association')

    title_template = "feeds/news_title.html"
    description_template = "feeds/news_content.html"

    def items(self):
        return NewsItem.objects.order_by('-publication_date')[:25]

    def author_name(self, obj):
        if obj:
            return obj.author

    def item_pubdate(self, item):
        if item:
            return item.publication_date

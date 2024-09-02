from django.contrib.syndication.views import Feed
from django.utils import timezone
from django.utils.translation import gettext_lazy as _l

from amelie.activities.models import Activity


class Activities(Feed):
    link = '/activities/'
    title = _l('IA Events')
    description = _l('Inter-Actief\'s activities in the coming weeks')

    title_template = "feeds/news_title.html"
    description_template = "feeds/news_content.html"

    def items(self):
        return Activity.objects.only_public().filter(begin__gte=timezone.now()).order_by('begin')[:25]

    def author_name(self, obj):
        return obj.organizer if obj else None

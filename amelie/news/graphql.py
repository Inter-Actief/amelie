import graphene

from graphene_django import DjangoObjectType
from django.utils.translation import gettext_lazy as _

from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.news.models import NewsItem


class NewsItemType(DjangoObjectType):
    class Meta:
        model = NewsItem
        description = "Type definition for a single News Item"
        filter_fields = {
            'id': ("exact", ),
            'title_nl': ("icontains", "iexact"),
            'title_en': ("icontains", "iexact"),
            'publication_date': ("exact", "gt", "lt"),
            'publisher': ("exact", ),
        }
        fields = [
            "id",
            "publication_date",
            "title_nl",
            "title_en",
            "slug",
            "introduction_nl",
            "introduction_en",
            "content_nl",
            "content_en",
            "publisher",
            "author",
            "attachments",
            "activities",
            "pinned",
        ]

    author = graphene.String(description=_("Message author"))
    publisher = graphene.String(description=_("Publishing committee"))

    # Translated fields in user's preferred language
    title = graphene.String(description=_("Message title (localized for user)"))
    introduction = graphene.String(description=_("Message introduction (localized for user)"))
    content = graphene.String(description=_("Message content (localized for user)"))

    def resolve_author(obj: NewsItem, info):
        return obj.author.incomplete_name()

    def resolve_publisher(obj: NewsItem, info):
        return obj.publisher.name

    def resolve_title(obj: NewsItem, info):
        return obj.title

    def resolve_introduction(obj: NewsItem, info):
        return obj.introduction

    def resolve_content(obj: NewsItem, info):
        return obj.content


class NewsQuery(graphene.ObjectType):
    news_item = graphene.Field(NewsItemType, id=graphene.ID())
    news_items = DjangoPaginationConnectionField(NewsItemType)

    def resolve_news_item(root, info, id):
        return NewsItem.objects.get(pk=id)


# Exports
GRAPHQL_QUERIES = [NewsQuery]
GRAPHQL_MUTATIONS = []

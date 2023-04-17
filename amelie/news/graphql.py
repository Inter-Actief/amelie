import graphene
from graphene_django_extras import DjangoObjectType, DjangoObjectField, DjangoFilterPaginateListField

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


class NewsQuery(graphene.ObjectType):
    news_item = DjangoObjectField(NewsItemType)
    news_items = DjangoFilterPaginateListField(NewsItemType)


# Exports
GRAPHQL_QUERIES = [NewsQuery]
GRAPHQL_MUTATIONS = []

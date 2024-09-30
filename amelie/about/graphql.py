from django.db.models import Q
from django.utils.translation import gettext_lazy as _
import graphene
from graphene_django import DjangoObjectType

from amelie.about.models import Page


class PageType(DjangoObjectType):
    class Meta:
        model = Page
        description = "Type definition for a single Page"
        fields = ["name_nl", "name_en", "slug_nl", "slug_en", "educational", "content_nl", "content_en", "last_modified"]

    name = graphene.String(description=_("Page name"))
    slug = graphene.String(description=_("Page slug"))
    content = graphene.String(description=_("Page content"))

    def resolve_name(obj: Page, info):
        return obj.name

    def resolve_slug(obj: Page, info):
        return obj.slug

    def resolve_content(obj: Page, info):
        return obj.content


class AboutQuery(graphene.ObjectType):
    page = graphene.Field(PageType, id=graphene.ID(), slug=graphene.String())

    def resolve_page(self, info, id=None, slug=None):
        if id is not None:
            return Page.objects.get(pk=id)
        if slug is not None:
            return Page.objects.get(Q(slug_en=slug) | Q(slug_nl=slug))
        return None


# Exports
GRAPHQL_QUERIES = [AboutQuery]
GRAPHQL_MUTATIONS = []

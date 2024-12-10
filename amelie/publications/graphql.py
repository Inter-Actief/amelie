from datetime import time

import graphene

from graphene_django import DjangoObjectType

from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.publications.models import Publication, PublicationType


class PublicationTypeType(DjangoObjectType):
    class Meta:
        model = PublicationType
        description = "Type definition for a type of Publication"
        fields = [
            "type_name",
            "description",
        ]


class PublicationItemType(DjangoObjectType):
    class Meta:
        model = Publication
        description = "Type definition for a single Publication"
        filter_fields = {
            'name': ("icontains", "iexact"),
            'date_published': ("exact", "gt", "lt"),
            'publication_type__type_name': ("icontains", "iexact"),
            'is_featured': ("exact",),
        }
        fields = [
            "id",
            "name",
            "description",
            "date_published",
            "publication_type",
            "thumbnail",
            "file",
            "is_featured",
            "public",
        ]

    def resolve_thumbnail(obj: Publication, info):
        return obj.get_thumbnail()


class PublicationQuery(graphene.ObjectType):
    publication = graphene.Field(PublicationItemType, id=graphene.ID())
    publications = DjangoPaginationConnectionField(PublicationItemType, id=graphene.ID())

    def resolve_publication(root, info, id):
        return Publication.objects.filter_public(info.context).get(pk=id)

    def resolve_publications(root, info, id=None, *args, **kwargs):
        """Find publications by ID"""
        qs = Publication.objects.filter_public(info.context)
        # Find the publication by its ID
        if id is not None:
            return qs.filter(pk=id)
        return qs


# Exports
GRAPHQL_QUERIES = [PublicationQuery]
GRAPHQL_MUTATIONS = []

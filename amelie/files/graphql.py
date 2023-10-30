import graphene
from graphene_django import DjangoObjectType

from amelie.files.models import Attachment


class AttachmentType(DjangoObjectType):
    class Meta:
        model = Attachment
        fields = [
            "file",
            "caption",
            "thumb_small",
            "thumb_medium",
            "thumb_large",
            "mimetype",
            "owner",
            "created",
            "modified",
            "thumb_small_height",
            "thumb_small_width",
            "thumb_medium_height",
            "thumb_medium_width",
            "thumb_large_height",
            "thumb_large_width",
            "public"
        ]


class FilesQuery(graphene.ObjectType):
    attachment = graphene.Field(AttachmentType, id=graphene.ID())

    def resolve_attachment(root, info, id):
        return Attachment.objects.get(pk=id)


GRAPHQL_QUERIES = [FilesQuery]
GRAPHQL_MUTATIONS = []

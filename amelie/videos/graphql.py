import graphene
import django_filters

from django.db import models
from django.utils.translation import gettext_lazy as _
from graphene_django import DjangoObjectType

from amelie.graphql.decorators import check_authorization
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.videos.models import BaseVideo


class VideoFilterSet(django_filters.FilterSet):
    class Meta:
        model = BaseVideo
        fields = {
            'title': ("icontains", "iexact"),
            'date_published': ("exact", "gt", "lt"),
            'publisher__name': ("icontains", "iexact"),
            'is_featured': ("exact",),
        }

    class VideoTypes(models.TextChoices):
        YOUTUBE = 'youtube', _('YouTube')
        STREAMING_IA = 'streamingia', _('Streaming.IA')
        PEERTUBE_IA = 'peertubeia', _('Video.IA')

    video_type = django_filters.ChoiceFilter(method='video_type_filter', choices=VideoTypes.choices)

    def video_type_filter(self, qs, filter_field, value):
        if value == "youtube":
            return qs.filter(youtubevideo__isnull=False)
        elif value == "streamingia":
            return qs.filter(streamingiavideo__isnull=False)
        elif value == "peertubeia":
            return qs.filter(peertubeiavideo__isnull=False)
        else:
            return qs


@check_authorization
class VideoType(DjangoObjectType):
    public_fields = [
        "video_id",
        "title",
        "description",
        "date_published",
        "thumbnail_url",
        "publisher",
        "is_featured",
        "public",
        "video_type",
        "video_url"
    ]
    class Meta:
        model = BaseVideo
        description = "Type definition for a single Video"
        filterset_class = VideoFilterSet
        fields = [
            "video_id",
            "title",
            "description",
            "date_published",
            "thumbnail_url",
            "publisher",
            "is_featured",
            "public",
        ]

    publisher = graphene.String(description=_("Publishing committee"))
    video_type = graphene.String(description=_("Video type (Youtube or IA)"))
    video_url = graphene.String(description=_("URL to the video"))

    def resolve_publisher(obj: BaseVideo, info):
        return obj.publisher.name

    def resolve_video_type(obj: BaseVideo, info):
        return obj.get_video_type()

    def resolve_video_url(obj: BaseVideo, info):
        return obj.get_absolute_url()


class VideoQuery(graphene.ObjectType):
    video = graphene.Field(VideoType, video_id=graphene.ID())
    videos = DjangoPaginationConnectionField(VideoType, video_id=graphene.ID())

    def resolve_video(root, info, video_id):
        return BaseVideo.objects.filter_public(info.context).get(video_id=video_id)

    def resolve_videos(root, info, video_id=None, *args, **kwargs):
        """Find videos by ID"""
        qs = BaseVideo.objects.filter_public(info.context)
        # Find the video by its Video ID
        if video_id is not None:
            return qs.filter(video_id=video_id)
        return qs


# Exports
GRAPHQL_QUERIES = [VideoQuery]
GRAPHQL_MUTATIONS = []

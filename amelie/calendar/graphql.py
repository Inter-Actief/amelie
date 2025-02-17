import graphene
from graphene_django import DjangoObjectType

from amelie.calendar.models import Event
from django.utils.translation import gettext_lazy as _

from amelie.files.graphql import AttachmentType
from amelie.graphql.decorators import check_authorization

# Specified separately from EventType.Meta to be able to use it in the Meta class of subclasses.
EVENT_TYPE_BASE_FIELDS = [
    "id",
    "begin",
    "end",
    "entire_day",
    "summary_nl",
    "summary_en",
    "promo_nl",
    "promo_en",
    "description_nl",
    "description_en",
    "organizer",
    "location",
    "public",
    "dutch_activity",
]
EVENT_TYPE_BASE_PUBLIC_FIELDS = [
    "id",
    "begin",
    "end",
    "entire_day",
    "summary_nl",
    "summary_en",
    "promo_nl",
    "promo_en",
    "description_nl",
    "description_en",
    "organizer",
    "location",
    "public",
    "dutch_activity",
    "attachments",
    "summary",
    "description",
    "promo",
    "description_short"
]


@check_authorization
class EventType(DjangoObjectType):
    """
    The event type used for GraphQL operations
    """
    public_fields = EVENT_TYPE_BASE_PUBLIC_FIELDS

    class Meta:
        # Make sure that this type is not actually being registered. But it can be used by other types as a base class.
        skip_registry = True

        model = Event
        fields = EVENT_TYPE_BASE_FIELDS

    attachments = graphene.List(AttachmentType, description="Attachment ids")
    summary = graphene.String(description=_('A summary of this activity in the preferred language of this user.'))
    description = graphene.String(
        description=_('A description of this activity in the preferred language of this user.'))
    promo = graphene.String(
        description=_('Promotional text for this activity in the preferred language of this user.'))
    description_short = graphene.String(description=_('A brief description of this activity (always in english).'))

    def resolve_attachments(self: Event, info):
        # `info.context` is the Django Request object in Graphene
        return self.attachments.filter_public(info.context)

    def resolve_summary(self: Event, info):
        return self.summary

    def resolve_description(self: Event, info):
        return self.description

    def resolve_promo(self: Event, info):
        return self.promo

    def resolve_description_short(self: Event, info):
        return self.description_short()


GRAPHQL_QUERIES = []
GRAPHQL_MUTATIONS = []

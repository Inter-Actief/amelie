import graphene
from graphene_django import DjangoObjectType

from amelie.calendar.models import Event
from django.utils.translation import gettext_lazy as _

from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField


class EventType(DjangoObjectType):
    """
    The event type used for GraphQL operations
    """
    class Meta:
        # Make sure that this type is not actually being registered. But it can be used by other types as a base class.
        skip_registry = True

        model = Event
        fields = [
            "pk",
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
            "callback_url",
            "organizer",
            "committee",
            "participation",
        ]

    attachments = graphene.List(graphene.ID, description="Attachment ids")
    summary = graphene.String(description=_('A summary of this activity in the preferred language of this user.'))
    description = graphene.String(
        description=_('A description of this activity in the preferred language of this user.'))
    promo = graphene.String(
        description=_('Promotional text for this activity in the preferred language of this user.'))
    description_short = graphene.String(description=_('A brief description of this activity (always in english).'))

    def resolve_attachments(self: Event, info):
        return self.attachments.values_list('id', flat=True)

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

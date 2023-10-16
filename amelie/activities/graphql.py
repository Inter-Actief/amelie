import graphene
from django_filters import FilterSet
from graphene_django import DjangoObjectType

from amelie.activities.models import Activity
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField


class ActivityFilterSet(FilterSet):
    class Meta:
        model = Activity
        fields = {
            'id': ("exact", ),
            'summary_nl': ("icontains", "iexact"),
            'summary_en': ("icontains", "iexact"),
            'begin': ("gt", "lt", "exact"),
            'end': ("gt", "lt", "exact"),
            'dutch_activity': ("exact", ),
        }


class ActivityType(DjangoObjectType):
    class Meta:
        model = Activity
        fields = [
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
            "attachments",
            "dutch_activity",
            "callback_url",
            "callback_secret_key"
        ]
        filterset_class = ActivityFilterSet


class ActivitiesQuery(graphene.ObjectType):
    activities = DjangoPaginationConnectionField(ActivityType, organizer=graphene.ID())

    def resolve_activities(self, info, organizer=None, *args, **kwargs):
        if organizer:
            return Activity.objects.filter(organizer__pk=organizer)
        return Activity.objects.all()

# Exports
GRAPHQL_QUERIES = [ActivitiesQuery]
GRAPHQL_MUTATIONS = []

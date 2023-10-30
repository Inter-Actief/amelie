import graphene
from django_filters import FilterSet
from graphene_django import DjangoObjectType

from amelie.activities.models import Activity, ActivityLabel
from amelie.files.models import Attachment
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
            "enrollment",
            "enrollment_begin",
            "enrollment_end",
            "maximum",
            "waiting_list_locked",
            "photos",
            "components",
            "price",
            "can_unenroll",
            "image_icon",
            "activity_label"
        ]
        filterset_class = ActivityFilterSet

    absolute_url = graphene.String()
    random_photo_url = graphene.String()
    photo_url = graphene.String()
    calendar_url = graphene.String()
    enrollment_open = graphene.Boolean()
    enrollment_closed = graphene.Boolean()
    can_edit = graphene.Boolean()
    places_available = graphene.Int()
    enrollment_full = graphene.Boolean()
    has_waiting_participants = graphene.Boolean()
    enrollment_almost_full = graphene.Boolean()
    has_enrollment_options = graphene.Boolean()
    has_costs = graphene.Boolean()
    # TODO: Figure out on how to use foreign keys here!

    def resolve_absolute_url(self: Activity, info):
        return self.get_absolute_url()

    def resolve_random_photo_url(self: Activity, info):
        return self.get_photo_url_random()

    def resolve_photo_url(self: Activity, info):
        return self.get_photo_url()

    def resolve_calendar_url(self: Activity, info):
        return self.get_calendar_url()

    def resolve_enrollment_open(self: Activity, info):
        return self.get_enrollment_open()

    def resolve_enrollment_closed(self: Activity, info):
        return self.get_enrollment_closed()

    def resolve_can_edit(self: Activity, info):
        if hasattr(info.context.user, 'person'):
            return self.can_edit(info.context.user.person)
        return False

    def resolve_places_available(self: Activity, info):
         return self.places_available()

    def resolve_enrollment_full(self: Activity, info):
        return self.enrollment_full()

    def resolve_has_waiting_participants(self: Activity, info):
        return self.has_waiting_participants()

    def resolve_enrollment_almost_full(self: Activity, info):
        return self.enrollment_almost_full()

    def resolve_has_enrollment_option(self: Activity, info):
        return self.has_enrollmentoption()

    def resolve_has_costs(self: Activity, info):
        return self.has_costs()

    # TODO: Write custom resolvers and attributes for functions defined on the events class (inherited by Activity)


class ActivityLabelType(DjangoObjectType):
    class Meta:
        model = ActivityLabel
        fields = [
            "name_en",
            "name_nl",
            "color",
            "icon",
            "explanation_en",
            "explanation_nl",
            "active"
        ]


class ActivitiesQuery(graphene.ObjectType):
    activities = DjangoPaginationConnectionField(ActivityType, organizer=graphene.ID())

    def resolve_activities(self, info, organizer=None, *args, **kwargs):
        if organizer:
            return Activity.objects.filter(organizer__pk=organizer)
        return Activity.objects.all()

# Exports
GRAPHQL_QUERIES = [ActivitiesQuery]
GRAPHQL_MUTATIONS = []

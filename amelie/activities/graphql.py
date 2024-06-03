import graphene
from django_filters import FilterSet
from django.utils.translation import gettext_lazy as _
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

    absolute_url = graphene.String(description=_('The absolute URL to an activity.'))
    random_photo_url = graphene.String(description=_('A URL to a random picture that was made at this activity.'))
    photo_url = graphene.String(description=_('A URL that points to the picture gallery for this activity.'))
    calendar_url = graphene.String(description=_('A link to the ICS file for this activity.'))
    enrollment_open = graphene.Boolean(description=_('Whether people can still enroll for this activity.'))
    enrollment_closed = graphene.Boolean(description=_('Whether people can no longer enroll for this activity.'))
    can_edit = graphene.Boolean(description=_('Whether the person that is currently signed-in can edit this activity.'))
    places_available = graphene.Int(description=_('The amount of open spots that are still available.'))
    enrollment_full = graphene.Boolean(description=_('Whether this activity is full.'))
    has_waiting_participants = graphene.Boolean(description=_('Whether this activity has any participations that are on the waiting list.'))
    enrollment_almost_full = graphene.Boolean(description=_('Whether this activity is almost full (<= 10 places left).'))
    has_enrollment_options = graphene.Boolean(description=_('If there are any options for enrollments.'))
    has_costs = graphene.Boolean(description=_('If there are any costs associated with this activity.'))
    summary = graphene.String(description=_('A summary of this activity in the preferred language of this user.'))
    description = graphene.String(description=_('A description of this activity in the preferred language of this user.'))
    promo = graphene.String(description=_('Promotional text for this activity in the preferred language of this user.'))
    description_short = graphene.String(description=_('A brief description of this activity (always in english).'))

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

    def resolve_summary(self: Activity, info):
        return self.summary

    def resolve_description(self: Activity, info):
        return self.description

    def resolve_promo(self: Activity, info):
        return self.promo1

    def resolve_description_short(self: Activity, info):
        return self.description_short()


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
    activity = graphene.Field(ActivityType, id=graphene.ID())

    def resolve_activities(self, info, organizer=None, *args, **kwargs):
        if organizer:
            return Activity.objects.filter(organizer__pk=organizer)
        return Activity.objects.all()

    def resolve_activity(self, info, id, *args, **kwargs):
        if id:
            return Activity.objects.get(pk=id)
        return None

# Exports
GRAPHQL_QUERIES = [ActivitiesQuery]
GRAPHQL_MUTATIONS = []

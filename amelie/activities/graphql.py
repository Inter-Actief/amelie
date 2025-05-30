import graphene
from django_filters import FilterSet
from django.utils.translation import gettext_lazy as _
from graphene_django import DjangoObjectType

from amelie.activities.models import Activity, ActivityLabel
from amelie.calendar.graphql import EventType, EVENT_TYPE_BASE_FIELDS, EVENT_TYPE_BASE_PUBLIC_FIELDS
from amelie.graphql.decorators import check_authorization
from amelie.graphql.helpers import is_logged_in
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField


class ActivityFilterSet(FilterSet):
    class Meta:
        model = Activity
        fields = {
            'summary_nl': ("icontains", "iexact"),
            'summary_en': ("icontains", "iexact"),
            'begin': ("gt", "lt", "exact"),
            'end': ("gt", "lt", "exact"),
            'dutch_activity': ("exact", ),
        }


@check_authorization
class ActivityType(EventType):
    public_fields = [
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
        "activity_label",
        "absolute_url",
        "random_photo_url",
        "photo_url",
        "calendar_url",
        "enrollment_open",
        "enrollment_closed",
        "can_edit",
        "enrollment_full",
        "enrollment_almost_full",
        "has_enrollment_options",
        "has_costs"
    ] + EVENT_TYPE_BASE_PUBLIC_FIELDS

    class Meta:
        model = Activity

        # Other fields are inherited from the EventType class
        fields = [
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
        ] + EVENT_TYPE_BASE_FIELDS
        filterset_class = ActivityFilterSet

    absolute_url = graphene.String(description=_('The absolute URL to an activity.'))
    random_photo_url = graphene.String(description=_('A URL to a random picture that was made at this activity.'))
    photo_url = graphene.String(description=_('A URL that points to the picture gallery for this activity.'))
    calendar_url = graphene.String(description=_('A link to the ICS file for this activity.'))
    enrollment_open = graphene.Boolean(description=_('Whether people can still enroll for this activity.'))
    enrollment_closed = graphene.Boolean(description=_('Whether people can no longer enroll for this activity.'))
    can_edit = graphene.Boolean(description=_('Whether the person that is currently signed-in can edit this activity.'))
    enrollment_full = graphene.Boolean(description=_('Whether this activity is full.'))
    enrollment_almost_full = graphene.Boolean(description=_('Whether this activity is almost full (<= 10 places left).'))
    has_enrollment_options = graphene.Boolean(description=_('If there are any options for enrollments.'))
    has_costs = graphene.Boolean(description=_('If there are any costs associated with this activity.'))

    def resolve_photos(self: Activity, info):
        # `info.context` is the Django Request object in Graphene
        return self.photos.filter_public(info.context)

    def resolve_absolute_url(self: Activity, info):
        return self.get_absolute_url()

    def resolve_random_photo_url(self: Activity, info):
        return self.get_photo_url_random()

    def resolve_photo_url(self: Activity, info):
        return self.get_photo_url()

    def resolve_calendar_url(self: Activity, info):
        return self.get_calendar_url()

    def resolve_enrollment_open(self: Activity, info):
        return self.enrollment_open()

    def resolve_enrollment_closed(self: Activity, info):
        return self.enrollment_closed()

    def resolve_can_edit(self: Activity, info):
        if is_logged_in(info):
            return self.can_edit(info.context.user.person)
        return False

    def resolve_enrollment_full(self: Activity, info):
        return self.enrollment_full()

    def resolve_enrollment_almost_full(self: Activity, info):
        return self.enrollment_almost_full()

    def resolve_has_enrollment_option(self: Activity, info):
        return self.has_enrollmentoptions()

    def resolve_has_costs(self: Activity, info):
        return self.has_costs()


@check_authorization
class ActivityLabelType(DjangoObjectType):
    public_fields = [
        "name_en",
        "name_nl",
        "color",
        "icon",
        "explanation_en",
        "explanation_nl",
        "active"
    ]
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
    activities = DjangoPaginationConnectionField(ActivityType, id=graphene.ID(), organizer=graphene.ID())
    activity = graphene.Field(ActivityType, id=graphene.ID())

    def resolve_activities(self, info, id=None, organizer=None, *args, **kwargs):
        qs = Activity.objects.filter_public(info.context)
        if organizer is not None:
            qs = qs.filter(organizer__pk=organizer)
        if id is not None:
            qs = qs.filter(id=id)
        return qs

    def resolve_activity(self, info, id, *args, **kwargs):
        if id is not None:
            return Activity.objects.filter_public(info.context).get(pk=id)
        return None

# Exports
GRAPHQL_QUERIES = [ActivitiesQuery]
GRAPHQL_MUTATIONS = []

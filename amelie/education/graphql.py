import graphene
from django_filters import FilterSet

from graphene_django import DjangoObjectType
from django.utils.translation import gettext_lazy as _
from graphene_django.forms.mutation import DjangoFormMutation

from amelie.education.forms import EducationalBouquetForm, EducationalBouquetFormGraphQL

from amelie.activities.graphql import ActivityLabelType
from amelie.calendar.graphql import EventType, EVENT_TYPE_BASE_FIELDS, EVENT_TYPE_BASE_PUBLIC_FIELDS
from amelie.graphql.decorators import check_authorization
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField

from amelie.education.models import Category, Page, EducationEvent


@check_authorization
class EducationPageType(DjangoObjectType):
    public_fields = [
        "id", "name_nl", "name_en", "name", "slug", "category",
        "content_nl", "content_en", "content", "last_changed", "position"
    ]
    class Meta:
        model = Page
        description = "Type definition for a single Education Page"
        filter_fields = {
            'id': ("exact",),
            'name_nl': ("icontains", "iexact"),
            'name_en': ("icontains", "iexact"),
        }
        fields = [
            "id", "name_nl", "name_en", "slug", "category", "content_nl", "content_en", "last_changed", "position"
        ]

    # Translated fields in user's preferred language
    name = graphene.String(description=_("Page name (localized for user)"))
    content = graphene.String(description=_("Page content (localized for user)"))

    def resolve_name(obj: Page, info):
        return obj.name

    def resolve_content(obj: Page, info):
        return obj.content


@check_authorization
class EducationPageCategoryType(DjangoObjectType):
    public_fields = ["id", "name_nl", "name_en", "name", "page_set"]
    class Meta:
        model = Category
        description = "Type definition for a single education page Category"
        filter_fields = {
            'id': ("exact",),
            'name_nl': ("icontains", "iexact"),
            'name_en': ("icontains", "iexact"),
        }
        fields = ["id", "name_nl", "name_en", "page_set"]

    # Translated fields in user's preferred language
    name = graphene.String(description=_("Category name (localized for user)"))

    def resolve_name(obj: Category, info):
        return obj.name


class EducationEventFilterSet(FilterSet):
    class Meta:
        model = EducationEvent
        fields = {
            'summary_nl': ("icontains", "iexact"),
            'summary_en': ("icontains", "iexact"),
            'begin': ("gt", "lt", "exact"),
            'end': ("gt", "lt", "exact"),
            'dutch_activity': ("exact",),
        }


@check_authorization
class EducationEventType(EventType):
    public_fields = [
        "education_organizer",
        "activity_label",
        "activity_type",
        "absolute_url"
    ] + EVENT_TYPE_BASE_PUBLIC_FIELDS

    class Meta:
        model = EducationEvent

        fields = [
            "education_organizer"
        ] + EVENT_TYPE_BASE_FIELDS

        filterset_class = EducationEventFilterSet

    activity_label = graphene.Field(ActivityLabelType)
    activity_type = graphene.String(description="The type of event")
    absolute_url = graphene.String(description="The absolute URL to this event")

    def resolve_activity_label(self: EducationEvent, info):
        return self.activity_label

    def resolve_activity_type(self: EducationEvent, info):
        return self.activity_type

    def resolve_absolute_url(self: EducationEvent, info):
        return self.get_absolute_url()


class EducationQuery(graphene.ObjectType):
    educationpage_category = graphene.Field(EducationPageCategoryType, id=graphene.ID())
    educationpage_categories = DjangoPaginationConnectionField(EducationPageCategoryType)

    educationpage = graphene.Field(EducationPageType, id=graphene.ID(), slug=graphene.String())
    educationpages = DjangoPaginationConnectionField(EducationPageType)

    education_event = graphene.Field(EducationEventType, id=graphene.ID())
    education_events = DjangoPaginationConnectionField(EducationEventType, id=graphene.ID())

    def resolve_educationpage_category(root, info, id=None):
        """Find education page category by ID"""
        if id is not None:
            return Category.objects.get(pk=id)
        return None

    def resolve_educationpage(root, info, id=None, slug=None):
        """Find education page by ID or slug"""
        if id is not None:
            return Page.objects.get(pk=id)
        if slug is not None:
            return Page.objects.get(slug=slug)
        return None

    def resolve_education_event(self, info, id=None):
        """Find education event by ID"""
        qs = EducationEvent.objects.filter_public(info.context)
        if id is not None:
            return qs.get(pk=id)
        return None

    def resolve_education_events(self, info, id=None, *args, **kwargs):
        """Find education event by ID"""
        qs = EducationEvent.objects.filter_public(info.context)
        if id is not None:
            return qs.filter(pk=id)
        return qs


class EducationalBouquetMutation(DjangoFormMutation):

    class Meta:
        form_class = EducationalBouquetFormGraphQL

class EducationMutation:
    educational_bouquet = EducationalBouquetMutation.Field()


# Exports
GRAPHQL_QUERIES = [EducationQuery]
GRAPHQL_MUTATIONS = [EducationMutation]

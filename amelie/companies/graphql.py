import graphene
from datetime import date
from django_filters import FilterSet
from graphene_django import DjangoObjectType

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from amelie.activities.graphql import ActivityLabelType
from amelie.calendar.graphql import EventType, EVENT_TYPE_BASE_FIELDS, EVENT_TYPE_BASE_PUBLIC_FIELDS
from amelie.companies.models import Company, WebsiteBanner, TelevisionBanner, VivatBanner, CompanyEvent
from amelie.graphql.decorators import check_authorization
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField


@check_authorization
class CompanyType(DjangoObjectType):
    public_fields = [
        "name_nl", "name_en", "name", "slug", "url", "logo", "logo_width", "logo_height", "profile_nl", "profile_en",
        "profile", "short_description_nl", "short_description_en", "short_description", "start_date", "end_date",
        "show_in_app", "app_logo", "app_logo_height", "app_logo_width"
    ]

    class Meta:
        model = Company
        description = "Type definition of a single Company"
        filter_fields = {
            "name_nl": ("icontains", "iexact"),
            "name_en": ("icontains", "iexact"),
        }
        fields = ["name_nl", "name_en", "slug", "url", "logo", "logo_width", "logo_height", "profile_nl", "profile_en",
                  "short_description_nl", "short_description_en", "start_date", "end_date", "show_in_app", "app_logo",
                  "app_logo_height", "app_logo_width"]

    name = graphene.String(description=_("Name of the company"))
    profile = graphene.String(description=_("Profile of the company"))
    short_description = graphene.String(description=_("Short description of the company"))


class CompanyEventFilterSet(FilterSet):
    class Meta:
        model = CompanyEvent
        fields = {
            'summary_nl': ("icontains", "iexact"),
            'summary_en': ("icontains", "iexact"),
            'begin': ("gt", "lt", "exact"),
            'end': ("gt", "lt", "exact"),
            'dutch_activity': ("exact", ),
        }


@check_authorization
class CompanyEventType(EventType):
    public_fields = [
        "company",
        "company_text",
        "company_url",
        "activity_label",
        "activity_type",
        "calendar_url",
        "absolute_url",
        "is_visible"
    ] + EVENT_TYPE_BASE_PUBLIC_FIELDS

    class Meta:
        model = CompanyEvent
        fields = [
            "company",
            "company_text",
            "company_url"
        ] + EVENT_TYPE_BASE_FIELDS
        filterset_class = CompanyEventFilterSet

    activity_label = graphene.Field(ActivityLabelType, description=_("The label that belongs to this activity"))
    activity_type = graphene.String(description=_("The type of activity"))
    calendar_url = graphene.String(description=_("The url to the ics for this activity"))
    absolute_url = graphene.String(description=_("The absolute URL to this event"))
    is_visible = graphene.Boolean(description=_("Whether this event is visible"))

    def resolve_activity_label(self: CompanyEvent, info):
        return self.activity_label

    def resolve_activity_type(self: CompanyEvent, info):
        return self.activity_type

    def resolve_calendar_url(self: CompanyEvent, info):
        return self.get_calendar_url()

    def resolve_absolute_url(self: CompanyEvent, info):
        return self.get_absolute_url()

    def resolve_is_visible(self: CompanyEvent, info):
        return self.is_visible()


@check_authorization
class WebsiteBannerType(DjangoObjectType):
    public_fields = ["picture", "name", "slug", "active", "url"]
    class Meta:
        model = WebsiteBanner
        description = "Type definition of a single Website Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "active", "url"]


@check_authorization
class TelevisionBannerType(DjangoObjectType):
    public_fields = ["picture", "name", "slug", "active"]
    class Meta:
        model = TelevisionBanner
        description = "Type definition of a single Television Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "active"]


@check_authorization
class VivatBannerType(DjangoObjectType):
    public_fields = ["picture", "name", "slug", "active", "url"]
    class Meta:
        model = VivatBanner
        description = "Type definition of a single Vivat Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "active", "url"]


class CompaniesQuery(graphene.ObjectType):
    company = graphene.Field(CompanyType, id=graphene.ID(), slug=graphene.String())
    companies = DjangoPaginationConnectionField(CompanyType)

    company_event = graphene.Field(CompanyEventType, id=graphene.ID())
    company_events = DjangoPaginationConnectionField(CompanyEventType, id=graphene.ID())

    website_banner = graphene.Field(WebsiteBannerType, id=graphene.ID(), slug=graphene.String())
    website_banners = DjangoPaginationConnectionField(WebsiteBannerType)

    television_banner = graphene.Field(TelevisionBannerType, id=graphene.ID(), slug=graphene.String())
    television_banners = DjangoPaginationConnectionField(TelevisionBannerType)

    vivat_banner = graphene.Field(VivatBannerType, id=graphene.ID(), slug=graphene.String())
    vivat_banners = DjangoPaginationConnectionField(VivatBannerType)

    def resolve_company(self, info, id=None, slug=None):
        if id is not None:
            return Company.objects.get(pk=id)
        if slug is not None:
            return Company.objects.get(slug=slug)
        return None

    def resolve_companies(self, info, *args, **kwargs):
        return Company.objects.filter(end_date__gte=date.today(), start_date__lte=date.today())

    def resolve_company_event(self, info, id=None):
        now = timezone.now()
        qs = CompanyEvent.objects.filter_public(info.context)
        # If the user is not board, filter only visible activities
        if not (hasattr(info.context, 'user') and info.context.user.is_authenticated and info.context.is_board):
            qs = qs.filter(visible_from__lt=now, visible_till__gt=now)

        if id is not None:
            return qs.get(pk=id)
        return None

    def resolve_company_events(self, info, id=None, *args, **kwargs):
        now = timezone.now()
        qs = CompanyEvent.objects.filter_public(info.context)
        # If the user is not board, filter only visible activities
        if not (hasattr(info.context, 'user') and info.context.user.is_authenticated and info.context.is_board):
            qs = qs.filter(visible_from__lt=now, visible_till__gt=now)

        if id is not None:
            qs = qs.filter(pk=id)
        return qs

    def resolve_website_banner(self, info, id=None, slug=None):
        if id is not None:
            return WebsiteBanner.objects.get(pk=id)
        if slug is not None:
            return WebsiteBanner.objects.get(slug=slug)
        return None

    def resolve_website_banners(self, info, *args, **kwargs):
        return WebsiteBanner.objects.filter(active=True)

    def resolve_television_banner(self, info, id=None, slug=None):
        if id is not None:
            return TelevisionBanner.objects.get(pk=id)
        if slug is not None:
            return TelevisionBanner.objects.get(slug=slug)
        return None

    def resolve_television_banners(self, info, *args, **kwargs):
        return TelevisionBanner.objects.filter(active=True)

    def resolve_vivat_banner(self, info, id=None, slug=None):
        if id is not None:
            return VivatBanner.objects.get(pk=id)
        if slug is not None:
            return VivatBanner.objects.get(slug=slug)
        return None

    def resolve_vivat_banners(self, info, *args, **kwargs):
        return VivatBanner.objects.filter(active=True)


# Exports
GRAPHQL_QUERIES = [CompaniesQuery]
GRAPHQL_MUTATIONS = []

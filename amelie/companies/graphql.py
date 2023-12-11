from django.utils.translation import gettext_lazy as _
import graphene
from graphene_django import DjangoObjectType

from amelie.companies.models import Company, WebsiteBanner, TelevisionBanner, VivatBanner
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField


# Note: Company events are implemented in the calendar module (amelie/calendar/graphql.py)

class CompanyType(DjangoObjectType):
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


class WebsiteBannerType(DjangoObjectType):
    class Meta:
        model = WebsiteBanner
        description = "Type definition of a single Website Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "start_date", "end_date", "active", "url"]


class TelevisionBannerType(DjangoObjectType):
    class Meta:
        model = TelevisionBanner
        description = "Type definition of a single Television Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "start_date", "end_date", "active"]


class VivatBannerType(DjangoObjectType):
    class Meta:
        model = VivatBanner
        description = "Type definition of a single Vivat Banner"
        filter_fields = {
            "name": ("icontains", "iexact"),
        }
        fields = ["picture", "name", "slug", "start_date", "end_date", "active", "url"]


class CompaniesQuery(graphene.ObjectType):
    company = graphene.Field(CompanyType, id=graphene.ID(), slug=graphene.String())
    companies = DjangoPaginationConnectionField(CompanyType)

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

    def resolve_website_banner(self, info, id=None, slug=None):
        if id is not None:
            return WebsiteBanner.objects.get(pk=id)
        if slug is not None:
            return WebsiteBanner.objects.get(slug=slug)
        return None

    def resolve_television_banner(self, info, id=None, slug=None):
        if id is not None:
            return TelevisionBanner.objects.get(pk=id)
        if slug is not None:
            return TelevisionBanner.objects.get(slug=slug)
        return None

    def resolve_vivat_banner(self, info, id=None, slug=None):
        if id is not None:
            return VivatBanner.objects.get(pk=id)
        if slug is not None:
            return VivatBanner.objects.get(slug=slug)
        return None


# Exports
GRAPHQL_QUERIES = [CompaniesQuery]
GRAPHQL_MUTATIONS = []

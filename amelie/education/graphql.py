import graphene

from graphene_django import DjangoObjectType
from django.utils.translation import gettext_lazy as _
from graphene_django.forms.mutation import DjangoFormMutation

from amelie import settings
from amelie.education.forms import EducationalBouquetForm
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField

from amelie.education.models import Category, Page
from amelie.iamailer import MailTask, Recipient


# Notice:
# Education Events are implemented in amelie/calendar/graphql.py as part of the general event interface


class EducationPageType(DjangoObjectType):
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


class EducationPageCategoryType(DjangoObjectType):
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


class EducationQuery(graphene.ObjectType):
    educationpage_category = graphene.Field(EducationPageCategoryType, id=graphene.ID())
    educationpage_categories = DjangoPaginationConnectionField(EducationPageCategoryType)

    educationpage = graphene.Field(EducationPageType, id=graphene.ID(), slug=graphene.String())
    educationpages = DjangoPaginationConnectionField(EducationPageType)

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


class EducationalBouquetMutation(DjangoFormMutation):

    class Meta:
        form_class = EducationalBouquetForm

class EducationMutation:
    educational_bouquet = EducationalBouquetMutation.Field()


# Exports
GRAPHQL_QUERIES = [EducationQuery]
GRAPHQL_MUTATIONS = [EducationMutation]

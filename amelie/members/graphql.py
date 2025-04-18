import graphene
import django_filters

from graphene_django import DjangoObjectType
from django_filters import FilterSet
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from amelie.graphql.decorators import check_authorization
from amelie.graphql.helpers import is_board, is_logged_in
from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.members.models import Committee, Function, CommitteeCategory


@check_authorization
class FunctionType(DjangoObjectType):
    public_fields = ["person", "committee", "function", "is_current_member"]
    board_fields = ["begin", "end"]

    class Meta:
        model = Function
        description = "Type definition for a single Function"
        fields = ["person", "committee", "function", "begin", "end"]

    person = graphene.String(description=_("Person name"))
    is_current_member = graphene.Boolean(description=_("This person is currently a member of this committee"))

    def resolve_person(obj: Function, info):
        return obj.person.incomplete_name()

    def resolve_is_current_member(obj: Function, info):
        return obj.end is None and obj.committee.abolished is None


class CommitteeFilterSet(FilterSet):
    class Meta:
        model = Committee
        fields = {
            'name': ("icontains", "iexact"),
            'founded': ("exact", "gt", "lt"),
            'abolished': ("exact", "gt", "lt"),
        }

    include_abolished = django_filters.BooleanFilter(method="include_abolished_filter", required=True)

    def include_abolished_filter(self, qs, filter_field, value):
        """
        Only active committees should be returned,
        unless specifically asked for by a board member or by someone who was a member of that committee
        """
        # If abolished committees are requested, we need to check if the user is logged in and allowed to see them
        if value and is_logged_in(self.request.user):
            # If user is a board member, include all committees
            if is_board(self.request.user):
                return qs
            # If user was a member of the committee, include active committees and committees in which they were active
            if self.request.user.person is not None:
                return qs.filter(
                    Q(abolished__isnull=True) | Q(function__person=self.request.user.person)
                ).distinct()
        # Else only return active committees
        return qs.filter(abolished__isnull=True)


@check_authorization
class CommitteeType(DjangoObjectType):
    public_fields = [
        "id",
        "name",
        "category",
        "parent_committees",
        "slug",
        "email",
        "founded",
        "abolished",
        "website",
        "information",
        "information_nl",
        "information_en",
        "logo",
        "group_picture",
        "function_set"
    ]

    class Meta:
        model = Committee
        description = "Type definition for a single Committee"
        filterset_class = CommitteeFilterSet
        fields = [
            "id",
            "name",
            "category",
            "parent_committees",
            "slug",
            "email",
            "founded",
            "abolished",
            "website",
            "information_nl",
            "information_en",
            "logo",
            "group_picture",
            "function_set",
        ]

    function_set = graphene.Field(graphene.List(FunctionType, description=_("Members of this committee")),
                                  include_past_members=graphene.Boolean())

    # Translated fields in user's preferred language
    information = graphene.String(description=_("Committee information (localized for user)"))

    def resolve_email(obj: Committee, info):
        """Resolves committee e-mail. Returns None if the e-mail is private and the user is not a board member."""
        if obj.private_email and not is_board(info):
            return None
        return obj.email

    def resolve_function_set(obj: Committee, info, include_past_members=False):
        """
        Only current members should be returned as part of a category,
        unless specifically asked for by a board member
        """
        # If past members are requested, only include them if the user is a board member
        if include_past_members and is_board(info):
            return obj.function_set.all()
        # Else only return current members
        return obj.function_set.filter(end__isnull=True)

    def resolve_information(obj: Committee, info):
        return obj.information


@check_authorization
class CommitteeCategoryType(DjangoObjectType):
    public_fields = ["id", "name", "slug", "committee_set"]

    class Meta:
        model = CommitteeCategory
        description = "Type definition for a single CommitteeCategory"
        filter_fields = {
            'name': ("icontains", "iexact"),
            'id': ("exact",),
        }
        fields = ["id", "name", "slug", "committee_set"]

    committee_set = graphene.Field(graphene.List(CommitteeType, description=_("Committees in this category")),
                                   include_abolished=graphene.Boolean())

    def resolve_committee_set(obj: CommitteeCategory, info, include_abolished=False):
        """
        Only active committees should be returned as part of a category,
        unless specifically asked for by a board member or by someone who was a member of that committee
        """
        # If abolished committees are requested, we need to check if the user is allowed to see them
        if include_abolished and is_logged_in(info):
            # If user is a board member, include all committees
            if info.context.is_board:
                return obj.committee_set.all()
            # If user was a member of the committee, include active committees and committees in which they were active
            if info.context.user.person is not None:
                return obj.committee_set.filter(
                    Q(abolished__isnull=True) | Q(function__person=info.context.person)
                ).distinct()
        # Else only return active committees
        return obj.committee_set.filter(abolished__isnull=True)


class MembersQuery(graphene.ObjectType):
    committee_category = graphene.Field(CommitteeCategoryType, id=graphene.ID(), slug=graphene.String())
    committee_categories = DjangoPaginationConnectionField(CommitteeCategoryType)

    committee = graphene.Field(CommitteeType, id=graphene.ID(), slug=graphene.String())
    committees = DjangoPaginationConnectionField(CommitteeType, id=graphene.ID(), slug=graphene.String())

    def resolve_committee_category(root, info, id=None, slug=None):
        """Find committee category by ID or slug"""
        if id is not None:
            return CommitteeCategory.objects.get(pk=id)
        if slug is not None:
            return CommitteeCategory.objects.get(slug=slug)
        return None

    def resolve_committee(root, info, id=None, slug=None):
        """Find committee by ID or slug, if the user is allowed to see it"""
        # Logged-in users can see more committees than non-logged-in users.
        if is_logged_in(info):
            # Board members can see all committees, including abolished ones
            if is_board(info):
                qs = Committee.objects

            # Logged-in users can see abolished committees that they were a part of
            else:
                qs = Committee.objects.filter(
                    Q(abolished__isnull=True) | Q(function__person=info.context.person)
                ).distinct()

        # Non-logged in users are only allowed to see active committees
        else:
            qs = Committee.objects.filter(abolished__isnull=True)

        # Find the committee by its ID or slug
        if id is not None:
            return qs.get(pk=id)
        if slug is not None:
            return qs.get(slug=slug)
        return None

    def resolve_committees(root, info, id=None, slug=None, *args, **kwargs):
        """Find committees by ID or slug, if the user is allowed to see it"""
        # Logged-in users can see more committees than non-logged-in users.
        if is_logged_in(info):
            # Board members can see all committees, including abolished ones
            if is_board(info):
                qs = Committee.objects

            # Logged-in users can see abolished committees that they were a part of
            else:
                qs = Committee.objects.filter(
                    Q(abolished__isnull=True) | Q(function__person=info.context.person)
                ).distinct()

        # Non-logged in users are only allowed to see active committees
        else:
            qs = Committee.objects.filter(abolished__isnull=True)

        # Find the committee by its ID or slug
        if id is not None:
            return qs.filter(pk=id)
        if slug is not None:
            return qs.filter(slug=slug)
        return qs


# Exports
GRAPHQL_QUERIES = [MembersQuery]
GRAPHQL_MUTATIONS = []

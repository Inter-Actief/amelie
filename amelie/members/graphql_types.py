import django_filters
from graphene_django import DjangoObjectType
from django_filters import FilterSet
from graphql import GraphQLError

import amelie.graphql.filters as custom_filters
from amelie.graphql.decorators import allow_only_self_or_board
from amelie.members.models import Person, Committee, Function, Dogroup, DogroupGeneration, Association, Student, \
    StudyPeriod, Employee, Photographer, CommitteeCategory


class DogroupFilterSet(FilterSet):
    class Meta:
        Model = Dogroup
        fields = ["name"]


class DogroupType(DjangoObjectType):
    class Meta:
        model = Dogroup
        description = "Type definition for a single Dogroup"
        filterset_class = DogroupFilterSet


class DogroupGenerationFilterSet(FilterSet):
    class Meta:
        model = DogroupGeneration
        fields = ["generation", "dogroup", "parents", "study", "mail_alias"]


class DogroupGenerationType(DjangoObjectType):
    class Meta:
        model = DogroupGeneration
        description = "Type definition for a single DogroupGeneration"
        filterset_class = DogroupGenerationFilterSet


class AssociationFilterSet(FilterSet):
    class Meta:
        model = Association
        fields = ["name", "studies"]


class AssociationType(DjangoObjectType):
    class Meta:
        model = Association
        description = "Type defintion for a single Association"
        filterset_class = AssociationFilterSet


class PersonFilterSet(FilterSet):
    sm_number = django_filters.CharFilter(method='sm_number_filter')
    underage = django_filters.BooleanFilter(method='underage_filter')
    also_old_members = django_filters.BooleanFilter(method='also_old_members_filter')
    only_old_members = django_filters.BooleanFilter(method='only_old_members_filter')
    has_not_paid = django_filters.BooleanFilter(method='has_not_paid_filter')
    was_member_in = custom_filters.NumberInFilter(method='was_member_in_filter')
    membership_type__in = custom_filters.NumberInFilter(method='membership_type__in_filter')
    study__in = custom_filters.NumberInFilter(method='study__in_filter')
    primary_studies = django_filters.CharFilter(method='primary_studies_filter')
    study_year__in = custom_filters.NumberInFilter(method='study_year__in_filter')
    is_employee = django_filters.BooleanFilter(method='is_employee_filter')
    department__in = custom_filters.NumberInFilter(method='department__in_filter')
    is_active = django_filters.BooleanFilter(method='is_active_filter')
    all_committees__contains = django_filters.CharFilter(method='all_committees__contains_filter')
    current_committees__contains = django_filters.CharFilter(method='current_committees__contains_filter')
    was_active_in = custom_filters.NumberInFilter(method='was_active_in_filter')
    has_dogroup = django_filters.BooleanFilter(method='has_dogroup_filter')
    dogroup__in = custom_filters.NumberInFilter(method='dogroup__in_filter')
    mandate_type__in = custom_filters.NumberInFilter(method='mandate_type__in_filter')
    mandate_number = django_filters.NumberFilter(method='mandate_number_filter')
    iban = django_filters.CharFilter(method='iban_filter')
    invert_preferences = django_filters.BooleanFilter(method='invert_preferences_filter')

    second_year_or_higher = django_filters.BooleanFilter(method='second_year_or_higher_filter')
    third_year_or_higher = django_filters.BooleanFilter(method='third_year_or_higher_filter')
    fourth_year_or_higher = django_filters.BooleanFilter(method='fourth_year_or_higher_filter')
    fifth_year_or_higher = django_filters.BooleanFilter(method='fifth_year_or_higher_filter')

    class Meta:
        model = Person
        fields = {
            "id": ["exact"],
            "first_name": ["icontains"],
            "last_name_prefix": ["icontains"],
            "last_name": ["icontains"],
            "initials": ["icontains"],
            "slug": ["icontains"],
            "gender": ["exact"],
            "preferred_language": ["exact"],
            "international_member": ["exact"],
            "email_address": ["icontains"],
            "account_name": ["icontains"],
            "nda": ["exact"],
            "preferences": ["exact", "in"],
            "user": ["exact"],
        }


class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        description = "Type definition for a single Person"
        filterset_class = PersonFilterSet
        only_fields = [
            "first_name", "last_name_prefix", "last_name", "initials", "slug",
            "picture", "notes", "gender", "date_of_birth",

            "preferred_language", "international_member",

            "email_address", "address", "postal_code", "city", "country", "telephone",

            "email_address_parents", "address_parents", "postal_code_parents",
            "city_parents", "country_parents", "can_use_parents_address",

            "account_name", "shell", "webmaster", "nda", "preferences", "user",

            "is_board"
        ]

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Object access denied.")
        if not user.is_superuser:
            return queryset.filter(user=info.context.user)
        return queryset

    @classmethod
    def get_object(cls, root, info, id):
        return cls.get_queryset(cls._meta.model.objects, info).get(id=id)

    @allow_only_self_or_board("context.user.person.id")
    def resolve_telephone(self, info):
        return self.telephone


class StudentFilterSet(FilterSet):
    class Meta:
        model = Student
        fields = ["person", "number"]


class StudentType(DjangoObjectType):
    class Meta:
        model = Student
        description = "Type definition for a single Student"
        filterset_class = StudentFilterSet


class StudyPeriodFilterSet(FilterSet):
    class Meta:
        model = StudyPeriod
        fields = ["student", "study", "begin", "end", "graduated", "dogroup"]


class StudyPeriodType(DjangoObjectType):
    class Meta:
        model = StudyPeriod
        description = "Type definition for a single StudyPeriod"
        filterset_class = StudyPeriodFilterSet


class EmployeeFilterSet(FilterSet):
    class Meta:
        model = Employee
        fields = ["person", "number", "end"]


class EmployeeType(DjangoObjectType):
    class Meta:
        model = Employee
        description = "Type definition for a single Employee"
        filterset_class = EmployeeFilterSet


class PhotographerFilterSet(FilterSet):
    class Meta:
        model = Photographer
        fields = ["first_name", "last_name_prefix", "last_name", "person"]


class PhotographerType(DjangoObjectType):
    class Meta:
        model = Photographer
        description = "Type definition for a single Photographer"
        filterset_class = PhotographerFilterSet


class CommitteeCategoryFilterSet(FilterSet):
    class Meta:
        model = CommitteeCategory
        fields = ["name", "slug"]


class CommitteeCategoryType(DjangoObjectType):
    class Meta:
        model = CommitteeCategory
        description = "Type definition for a single CommitteeCategory"
        filterset_class = CommitteeCategoryFilterSet


class CommitteeFilterSet(FilterSet):
    class Meta:
        model = Committee
        exclude = ["logo", "group_picture"]


class CommitteeType(DjangoObjectType):
    class Meta:
        model = Committee
        description = "Type definition for a single Committee"
        filterset_class = CommitteeFilterSet


class FunctionFilterSet(FilterSet):
    class Meta:
        model = Function
        fields = ["person", "committee", "function", "note", "begin", "end"]


class FunctionType(DjangoObjectType):
    class Meta:
        model = Function
        description = "Type definition for a single Function"
        filterset_class = FunctionFilterSet

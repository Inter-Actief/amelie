import graphene

from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.members.graphql_types import PersonType, CommitteeType, FunctionType, DogroupType, DogroupGenerationType, \
    AssociationType, StudentType, StudyPeriodType, EmployeeType, PhotographerType, CommitteeCategoryType


class MembersQuery(graphene.ObjectType):
    dogroup = graphene.Field(DogroupType, id=graphene.ID())
    dogroups = DjangoPaginationConnectionField(DogroupType)

    dogroupGeneration = graphene.Field(DogroupGenerationType, id=graphene.ID())
    dogroupGenerations = DjangoPaginationConnectionField(DogroupGenerationType)

    association = graphene.Field(AssociationType, id=graphene.ID())
    associations = DjangoPaginationConnectionField(AssociationType)

    person = graphene.Field(PersonType, id=graphene.ID())
    persons = DjangoPaginationConnectionField(PersonType)

    student = graphene.Field(StudentType, id=graphene.ID())
    students = DjangoPaginationConnectionField(StudentType)

    studyPeriod = graphene.Field(StudyPeriodType, id=graphene.ID())
    studyPeriods = DjangoPaginationConnectionField(StudyPeriodType)

    employee = graphene.Field(EmployeeType, id=graphene.ID())
    employees = DjangoPaginationConnectionField(EmployeeType)

    photographer = graphene.Field(PhotographerType, id=graphene.ID())
    photographers = DjangoPaginationConnectionField(PhotographerType)

    committeeCategory = graphene.Field(CommitteeCategoryType, id=graphene.ID())
    committeeCategories = DjangoPaginationConnectionField(CommitteeCategoryType)

    committee = graphene.Field(CommitteeType, id=graphene.ID())
    committees = DjangoPaginationConnectionField(CommitteeType)

    function = graphene.Field(FunctionType, id=graphene.ID())
    functions = DjangoPaginationConnectionField(FunctionType)

    def resolve_person(root, *args, **kwargs):
        return PersonType.get_object(root, *args, **kwargs)


# Exports
GRAPHQL_QUERIES = [MembersQuery]
GRAPHQL_MUTATIONS = []

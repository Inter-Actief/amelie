import graphene

from amelie.graphql.pagination.connection_field import DjangoPaginationConnectionField
from amelie.members.graphql_types import PersonType, CommitteeType


class MembersQuery(graphene.ObjectType):
    person = graphene.Field(PersonType, id=graphene.ID())
    persons = DjangoPaginationConnectionField(PersonType)

    committee = graphene.Field(CommitteeType, id=graphene.ID())
    committees = DjangoPaginationConnectionField(CommitteeType)

    def resolve_person(root, *args, **kwargs):
        return PersonType.get_object(root, *args, **kwargs)


# Exports
GRAPHQL_QUERIES = [MembersQuery]
GRAPHQL_MUTATIONS = []

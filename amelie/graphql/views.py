from graphene_django.views import GraphQLView


class IAGraphQLView(GraphQLView):
    def execute_graphql_request(
        self, request, data, query, variables, operation_name, show_graphiql=False
    ):
        return super().execute_graphql_request(request, data, query, variables, operation_name, show_graphiql=show_graphiql)

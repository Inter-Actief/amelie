import importlib
import logging

import graphene
from django.conf import settings
from graphene_django_extras import all_directives

import amelie.graphql.auth as auth
import amelie.graphql.i18n as i18n

logger = logging.getLogger("amelie.graphql")

# Basic GraphQL Query and Mutation schemas
query_subclasses = [i18n.InternationalizationQuery, auth.AuthenticationQuery, graphene.ObjectType]
mutation_subclasses = [i18n.InternationalizationMutation, auth.AuthenticationMutation, graphene.ObjectType]

# Add debug property if the debug toolbar is enabled
if settings.DEBUG_TOOLBAR:
    from graphene_django.debug import DjangoDebug

    class DebugQuery(graphene.ObjectType):
        debug = graphene.Field(DjangoDebug, name='_debug')

    query_subclasses = [DebugQuery] + query_subclasses

# Add dynamic queries and mutations from apps
for schema in settings.GRAPHQL_SCHEMAS:
    logger.debug(f"Loading GraphQL schema {schema}...")
    schema_module = importlib.import_module(schema)
    try:
        query_subclasses = schema_module.GRAPHQL_QUERIES + query_subclasses
    except AttributeError:
        raise AttributeError(f"Schema \"{schema}\" does not have the required attribute GRAPHQL_QUERIES")
    try:
        mutation_subclasses = schema_module.GRAPHQL_MUTATIONS + mutation_subclasses
    except AttributeError:
        raise AttributeError(f"Schema \"{schema}\" does not have the required attribute GRAPHQL_MUTATIONS")
    logger.debug(f"Loaded GraphQL schema {schema} successfully.")

# Construct types
Query = type('GraphQLQuery', tuple(query_subclasses), {})
Mutation = type('GraphQLMutation', tuple(mutation_subclasses), {})

# Initialize schema
schema = graphene.Schema(query=Query, mutation=Mutation, directives=all_directives)

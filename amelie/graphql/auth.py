import graphql_jwt
from django.contrib.auth import get_user_model

import graphene
from graphene_django import DjangoObjectType


class UserType(DjangoObjectType):
    class Meta:
        model = get_user_model()
        description = "Type definition for a single User"
        exclude = ("password", )


class AuthenticationQuery(graphene.ObjectType):
    me = graphene.Field(
        UserType,
        description="Information about the currently logged in user"
    )

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        return user


class AuthenticationMutation(graphene.ObjectType):
    verify_token = graphql_jwt.Verify.Field(
        description="Check if an authentication token is valid"
    )

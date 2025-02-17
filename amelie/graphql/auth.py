import graphql_jwt
from django.contrib.auth import get_user_model

import graphene
from graphene_django import DjangoObjectType

from amelie.graphql.decorators import check_authorization


@check_authorization
class UserType(DjangoObjectType):
    public_fields = ["id", "last_login", "is_superuser", "username", "first_name", "last_name", "email",
                     "is_staff", "is_active", "date_joined", "groups"]

    class Meta:
        model = get_user_model()
        description = "Type definition for a single User"
        fields = ["id", "last_login", "is_superuser", "username", "first_name", "last_name", "email",
                  "is_staff", "is_active", "date_joined", "groups"]


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

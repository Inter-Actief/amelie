import graphene

from django.utils.translation import check_for_language


class SetLanguageMutation(graphene.Mutation):
    class Arguments:
        language_code = graphene.String(required=True)

    result = graphene.Boolean()
    language = graphene.String()

    @classmethod
    def mutate(cls, root, info, language_code):
        # Language setting code copied from Django set_language view.
        # Source: https://github.com/django/django/blob/main/django/views/i18n.py#L30
        # Graphene mutation does not have access to the response object, so cookie is set using a middleware.
        # Find the middleware in amelie.tools.middleware.LanguageConfigMiddleware
        request = info.context
        active_language = request.LANGUAGE_CODE
        result = False
        if language_code and check_for_language(language_code):
            request.set_language_cookie = language_code  # Picked up by the `amelie.tools.middleware.LanguageConfigMiddleware` later.
            active_language = language_code
            result = True
        return SetLanguageMutation(result=result, language=active_language)


class InternationalizationQuery(graphene.ObjectType):
    language_code = graphene.String(
        description="The currently active language"
    )

    def resolve_language_code(self, info):
        return info.context.LANGUAGE_CODE


class InternationalizationMutation(graphene.ObjectType):
    set_language = SetLanguageMutation.Field()

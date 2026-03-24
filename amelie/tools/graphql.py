import graphene
from django.utils.translation import gettext_lazy as _
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url

class CaptchaType(graphene.ObjectType):
    key = graphene.String(description=_("The key for this specific CAPTCHA challenge"))
    image = graphene.String(description=_("The URL to the generated image for this CAPTCHA"))


class CaptchaInput(graphene.InputObjectType):
    key = graphene.String(description=_("The key for this specific CAPTCHA challenge"), required=True)
    response = graphene.String(description=_("The response to the CAPTCHA challenge"), required=True)


class CaptchaQuery(graphene.ObjectType):
    generate_captcha = graphene.Field(CaptchaType)

    def resolve_generate_captcha(root, info):
        generated_key = CaptchaStore.generate_key()
        return CaptchaType(key=generated_key, image=captcha_image_url(generated_key))



GRAPHQL_QUERIES = [CaptchaQuery]
GRAPHQL_MUTATIONS = []

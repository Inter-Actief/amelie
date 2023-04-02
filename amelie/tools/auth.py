from django.conf import settings
from django.contrib.auth.models import User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from amelie.members.models import Person


class IAOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        """Block login if the OIDC claims do not give a value for the Inter-Actief account username"""
        verified = super(IAOIDCAuthenticationBackend, self).verify_claims(claims)
        has_username = claims.get('preferred_username', None) is not None
        return verified and has_username

    def filter_users_by_claims(self, claims):
        username = claims.get('preferred_username')

        if not username:
            return self.UserModel.objects.none()

        if not settings.DEBUG and username.lower() in settings.LOGIN_NOT_ALLOWED_USERNAMES:
            return self.UserModel.objects.none()

        # Find Person by IA account name
        try:
            person = Person.objects.get(account_name=username)
        except Person.DoesNotExist:
            # Login was successful, but person was not found (should not happen)
            person = None

        if person:
            # Get or create the user object for this person
            user, created = person.get_or_create_user(username)
        else:
            # Get or create the user object for this unknown user (not linked to a Person)
            user, created = User.objects.get_or_create(username=username)
        return [user]

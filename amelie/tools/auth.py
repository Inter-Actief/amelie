from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from amelie.tools.user import get_user_by_username


class IAOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        """Block login if the OIDC claims do not give a value for the Inter-Actief account username"""
        verified = super(IAOIDCAuthenticationBackend, self).verify_claims(claims)
        has_username = claims.get('preferred_username', None) is not None
        return verified and has_username

    def filter_users_by_claims(self, claims):
        username = claims.get('preferred_username')
        user = get_user_by_username(username)
        return [user]

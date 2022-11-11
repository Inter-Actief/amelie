import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from djangosaml2.backends import Saml2Backend
from django.utils.translation import gettext_lazy as _

from amelie.members.models import Person, Study


def ldap_login(username, password):
    """
    Check the username/password against an LDAP-server.
    Returns None, True if a person is not known, but has logged in successfully.
    """
    import ldap
    try:
        constr = u"ldaps://%s:636/" % settings.LDAP_HOST
        l = ldap.initialize(constr, bytes_mode=False)
        l.protocol_version = ldap.VERSION3
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.simple_bind_s('%s@ia.utwente.nl' % username, password)
        if l.whoami_s():
            l.unbind()
            try:
                return Person.objects.get(account_name=username), True
            except Person.DoesNotExist:
                # Person not found, but was logged in successfully
                return None, True
        else:
            l.unbind()
            return None, False  # Anonymous login that failed
    except ldap.LDAPError:  # Password is not correct
        return None, False


class IALoginBackend(ModelBackend):
    """
    Authenticate against the Inter-Actief backend (IA-domain)
    """

    supports_object_permissions = False
    supports_anonymous_user = False
    supports_inactive_user = False

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate against the Inter-Actief domain using the username
        """

        # If not running in DEBUG mode, block login for certain AD usernames that are only
        # used in development, or that generally should not be able to log in to the website.
        # For example bob, Visitor or beun
        if not settings.DEBUG and (username is not None and username.lower() in settings.LOGIN_NOT_ALLOWED_USERNAMES):
            return None

        person, success = ldap_login(username, password)

        if not success:  # credentials are incorrect, fail
            return None

        if person:
            user, created = person.get_or_create_user(username)
            return user

        user, created = User.objects.get_or_create(username=username)  # create user object for the user
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class AmelieSAML2Backend(Saml2Backend):
    """
    Backend used to login via UTwente SAML.
    """

    def __init__(self):
        self.request = None
        super(AmelieSAML2Backend, self).__init__()

    def authenticate(self, request, *args, **kwargs):
        self.request = request
        return super(AmelieSAML2Backend, self).authenticate(request, *args, **kwargs)

    def get_or_create_user(self, user_lookup_key, user_lookup_value, create_unknown_user,
                           idp_entityid, attributes, attribute_mapping, request):
        """
        Returns the Django User that belongs to the user that just logged in.
        We can assume that the user has properly authenticated to the SAML backend here.
        :param create_unknown_user: If a user should be created if it does not exist.
        :param user_lookup_value: The SAML2 username
        :param attributes: User attributes
        :param attribute_mapping: Mapping from SAML attribute to Django attribute
        :param user_lookup_key: Not used ('uid')
        :param idp_entityid: Not used
        :param request: Not used
        :return: The user, or None and created boolean
        """

        try:
            user_id = int(user_lookup_value.lower()[1:])
            user_type = user_lookup_value.lower()[0]

            person = None
            if user_type == 's':
                person = Person.objects.get(student__number=user_id)
            elif user_type == 'm':
                person = Person.objects.get(employee__number=user_id)

            if person is not None and person.is_member():
                # Since UT years are from sept-aug and our year is from jul-jun, there are two months overlap.
                # Never verify users in July or August, as this could allow members who are done studying to get an
                # extra year as study long.
                if not person.membership.is_verified() and datetime.date.today().month not in [7, 8]:
                    primary_studies = Study.objects.filter(primary_study=True).values_list('abbreviation', flat=True)
                    if attributes.get('ou') is not None:
                        studies = attributes.get('ou')[0].split(',')
                    elif attributes.get('department') is not None:
                        studies = attributes.get('department')[0].split(',')
                    else:
                        studies = []
                    for study in studies:
                        if study in primary_studies:
                            person.membership.verify()
                            break
                if create_unknown_user:
                    return person.get_or_create_user(username=user_lookup_value.lower())
                elif person.has_user():
                    return person.user, False

        except Person.DoesNotExist:
            pass

        # Person doesn't exist and should not be logged in, inform the user
        messages.error(self.request, _("You were successfully logged in, but no account could be found. This might be "
                                       "the case if you aren't a member yet, or aren't a member anymore. "
                                       "If you want to become a member you can contact the board."))

        return None, False

    def _update_user(self, user, attributes, attribute_mapping, force_save=False):
        """
        Override function as we do not want the user to be updated after every SAML login.
        We might want to use this later to store the department from the SAML attributes
        :param user:
        :param attributes:
        :param attribute_mapping:
        :param force_save:
        :return:
        """
        return user

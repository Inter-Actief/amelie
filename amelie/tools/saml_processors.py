from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from djangosaml2idp.models import ServiceProvider
from djangosaml2idp.processors import BaseProcessor, NameIdBuilder

from amelie.claudia.models import ExtraPerson, Mapping, Event
from amelie.members.models import Person
from amelie.tools.encodings import normalize_to_ascii


class AmelieActiveMembersProcessor(BaseProcessor):
    def has_access(self, request):
        try:
            person = Person.objects.get(user=request.user)
            if person.is_active_member():
                return True


            mp = Mapping.wrap(person)

            # If this is an old-board-member that wants to access their old account, allow it
            group = Mapping.objects.get(pk=settings.CLAUDIA_GSUITE['OLD_BOARD_MAPPING_ID'])
            if group in mp.groups('all'):
                return True

            # People that are in their grace period after they have become an inactive member
            # should still be able to log into GSuite.
            has_deletion_events = Event.objects.filter(mapping=mp, type="DELETE_GSUITE_USER").exists()

            return has_deletion_events

        except Person.DoesNotExist:
            # It could also be an ExtraPerson
            pass

        try:
            person = ExtraPerson.objects.get(adname=request.user.username)
            if person.is_active():
                return True

        except ExtraPerson.DoesNotExist:
            # Ok, I don't know.
            pass

        return False

    def get_user_id(self, user, name_id_format: str, service_provider: ServiceProvider, idp_config) -> str:
        """ Get identifier for a user.
        """
        user_id = self.get_username(user)

        # returns in a real name_id format
        return NameIdBuilder.get_nameid(user_id, name_id_format, sp=service_provider, user=user)

    def get_username(self, user):
        email = None

        try:
            person = Person.objects.get(user=user)
            person_mp = Mapping.wrap(person)

            # Get the group for GSuite NL members
            group = Mapping.objects.get(pk=settings.CLAUDIA_GSUITE['OLD_BOARD_MAPPING_ID'])

            # Old board members
            if person_mp in group.members():
                # firstname.lastname@inter-actief.nl
                last_name = normalize_to_ascii(person.get_surname()).replace(' ', '').replace("'", '')
                name = normalize_to_ascii(person.get_givenname()).replace(' ', '').replace("'", '')
                username = "{}.{}".format(name, last_name).lower()
                email = "{}@{}".format(username, settings.CLAUDIA_GSUITE['OLD_BOARD_DOMAIN'])

            else:
                email = "{}@{}".format(person.get_adname(), settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])

        except Person.DoesNotExist:
            # It could also be an ExtraPerson
            pass

        try:
            person = ExtraPerson.objects.get(adname=user.username)
            if person.email:
                email = person.email

        except ExtraPerson.DoesNotExist:
            # Ok, I don't know.
            pass

        if not email:
            raise PermissionDenied(_("Unknown user in system."))

        return email


class AmelieAllMembersProcessor(BaseProcessor):
    def has_access(self, request):
        try:
            person = Person.objects.get(user=request.user)

            # Allow all members with an active membership
            if person.is_member():
                return True

            # Allow all active members (even if they don't have an active membership)
            if person.is_active_member():
                return True

            # Else, no access
            return False

        except Person.DoesNotExist:
            # It could also be an ExtraPerson
            pass

        try:
            person = ExtraPerson.objects.get(adname=request.user.username)
            if person.is_active():
                return True

        except ExtraPerson.DoesNotExist:
            # Ok, I don't know.
            pass

        return False

    def get_user_id(self, user, name_id_format: str, service_provider: ServiceProvider, idp_config) -> str:
        """ Get identifier for a user.
        """
        user_id = self.get_username(user)

        # returns in a real name_id format
        return NameIdBuilder.get_nameid(user_id, name_id_format, sp=service_provider, user=user)

    def get_username(self, user):
        return user.username

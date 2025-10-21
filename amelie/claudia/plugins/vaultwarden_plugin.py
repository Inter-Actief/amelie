"""Plugin for managing Vaultwarden accounts."""
import logging
import random
import string

from django.conf import settings
from vaultwarden.clients.vaultwarden import VaultwardenAdminClient
from vaultwarden.models.enum import CipherType, OrganizationUserType
from vaultwarden.models.bitwarden import get_organization, Organization

from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.tools import unify_mail

logger = logging.getLogger(__name__)


class VaultwardenPlugin(ClaudiaPlugin):
    """
    Vaultwarden plugin for Claudia

    Manages the link between Claudia-objects and Vaultwarden users and groups

    Author: Mihai Pop
    """

    def verify_mapping(self, claudia, mp, fix=False):
        """
        Verify Vaultwarden account of mapping

        :param Claudia claudia: Claudia object.
        :param Mapping mp: Mapping object to verify.
        :param bool fix: Fixes should be applied.
        """
        changes = []

        logger.debug("Verifying Vaultwarden data of {} (cid: {})".format(mp.name, mp.id))

        server = settings.CLAUDIA_VAULTWARDEN['SERVER']
        token = settings.CLAUDIA_VAULTWARDEN['TOKEN']

        client = VaultwardenAdminClient(url=server, admin_secret_token=token)

        if not fix:
            logger.debug("No changes will me made to internal attributes")

        if mp.is_person():
            logger.debug("Mapping is a person, checking Vaultwarden account and its groups.")
            if mp.adname:
                # Get groups a user should be in
                vaultwarden_user = client.get_user(mp.email)
                organizations = vaultwarden_user.Organizations

                # Check if user has account
                user = self.get_user(client, mp.email)
                if user:
                    logger.debug("Vaultwarden user for {} exists.".format(mp.email))

                # Create account if necessary
                if user is None and organizations and mp.needs_account():
                    logger.debug("Vaultwarden user for {} does not exist, creating.".format(mp.email))
                    passwd = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(40))
                    if fix:
                        try:
                            user = client.users.invite(unify_mail(mp.adname))
                            changes.append(('account', '{} created'.format(user.username)))
                            claudia.notify_Vaultwarden_created(mp, mp.adname)
                        except Exception as e:
                            logger.error("Vaultwarden user creation for {} failed: {}".format(mp.adname))

                # Change organizations if necessary
                if user is not None:
                    vaultwarden_groups = self.get_groups_for_member(client, user)

                    def _match(group):
                        return group.path in [g.email for g in organizations]

                    def _remove(group):
                        return group.path not in [g.email for g in organizations]

                    def _add(group):
                        return group.email not in [g.path for g in vaultwarden_groups]

                    # Filter lists to create add/remove lists
                    remove = list(filter(_remove, vaultwarden_groups))
                    add = list(filter(_add, organizations))
                    matched = list(filter(_match, vaultwarden_groups))

                    if len(matched) > 0:
                        logger.debug("Matched groups: %r" % matched)
                    if len(remove) > 0:
                        changes.append(('groups', ['-%s' % group.path for group in remove]))
                    if len(add) > 0:
                        changes.append(('groups', ['+%s' % group.adname for group in add]))

                    # Remove group members
                    for group in remove:
                        logger.debug("{} should not be in group {}".format(user.name, group.name))
                        if fix:
                            # noinspection PyUnresolvedReferences
                            group.members.delete(user.id)

                    # Add group members
                    for group in add:
                        logger.debug("{} should be in group {}".format(user.name, group.name))
                        Vaultwarden_group = self.get_group(git, group.adname)
                        if fix:
                            if Vaultwarden_group:
                                # noinspection PyUnresolvedReferences
                                Vaultwarden_group.members.create({
                                    'user_id': user.id,
                                    'access_level': Vaultwarden.DEVELOPER_ACCESS,
                                })
                            else:
                                logger.error("Could not find Vaultwarden group {} with id {}!".format(group.name, group.id))

        if mp.is_group() and mp.extra_data().get('Vaultwarden', False):
            logger.debug("Mapping is a group and should have a Vaultwarden group, checking if the group exists in Vaultwarden.")

            if mp.adname:
                # Check if committee has a group
                group = self.get_group(git, mp.adname)

                if group:
                    logger.debug("Vaultwarden group for {} exists.".format(mp.adname))

                if group is None and mp.needs_account():
                    logger.debug("Vaultwarden group for {} does not exist, creating.".format(mp.adname))
                    if fix:
                        group = git.groups.create({
                            'name': mp.name,
                            'path': mp.adname,
                        })
                        if group:
                            changes.append(('group', '{} created'.format(group.path)))
                            claudia.notify_Vaultwarden_created(mp, mp.adname)
                        else:
                            logger.error("Vaultwarden group creation for {} failed.".format(mp.adname))

        if changes:
            claudia.notify_Vaultwarden_changed(mp, mp.adname, changes)

    @staticmethod
    def get_organization(client, name):
        """
        Get the group information for a given name.

        Returns None if the group is not found.
        """
        return client.get_group(name)

    @staticmethod
    def get_organizations_for_member(user):
        """
        Get the groups for a given user.

        Returns a list of groups.
        """
        return user.Organizations
        

    @staticmethod
    def get_user(client, username):
        """
        Get the user information for a given username.

        Returns None if the user is not found.
        """
        return client.get_user(username)

    @staticmethod
    def get_all_users(client):
        """
        Get all users in Vaultwarden.

        Returns a list of users.
        """
        return client.get_users()
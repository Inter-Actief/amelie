"""Plugin for managing GitLab accounts."""
import logging
import random
import string

from django.conf import settings
import gitlab

from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.tools import unify_mail

logger = logging.getLogger(__name__)


class GitlabPlugin(ClaudiaPlugin):
    """
    GitLab plugin for Claudia

    Manages the link between Claudia-objects and Gitlab users and groups

    Author: k.j.alberts
    """

    def verify_mapping(self, claudia, mp, fix=False):
        """
        Verify GitLab account of mapping

        :param Claudia claudia: Claudia object.
        :param Mapping mp: Mapping object to verify.
        :param bool fix: Fixes should be applied.
        """
        changes = []

        logger.debug("Verifying Gitlab data of {} (cid: {})".format(mp.name, mp.id))

        server = settings.CLAUDIA_GITLAB['SERVER']
        token = settings.CLAUDIA_GITLAB['TOKEN']
        verify_ssl = settings.CLAUDIA_GITLAB['VERIFY_SSL']

        git = gitlab.Gitlab(server, private_token=token, ssl_verify=verify_ssl)

        if not fix:
            logger.debug("No changes will me made to internal attributes")

        if mp.is_person():
            logger.debug("Mapping is a person, checking GitLab account and its groups.")
            if mp.adname:
                # Get groups a user should be in
                groups = [g for g in mp.all_groups('ad') if g.is_group() and g.extra_data().get('gitlab', False) and g.adname and (self.get_group(git, g.adname) is not None)]

                # Check if user has account
                user = self.get_user(git, mp.adname)
                if user:
                    logger.debug("GitLab user for {} exists.".format(mp.adname))

                # Create account if necessary
                if user is None and groups and mp.needs_account():
                    logger.debug("GitLab user for {} does not exist, creating.".format(mp.adname))
                    passwd = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(40))
                    if fix:
                        user = git.users.create({
                            'email': unify_mail(mp.adname),
                            'username': mp.adname,
                            'name': mp.name,
                            'password': passwd,
                            'extern_uid': "CN={},OU=Gebruikers,OU=Inter-Actief,DC=ia,DC=utwente,DC=nl".format(mp.name),
                            'provider': "ldapmain",
                            'can_create_group': False,
                            'skip_confirmation': True,
                        })
                        if user:
                            changes.append(('account', '{} created'.format(user.username)))
                            claudia.notify_gitlab_created(mp, mp.adname)
                        else:
                            logger.error("GitLab user creation for {} failed.".format(mp.adname))

                # Change groups if necessary
                if user is not None:
                    gitlab_groups = self.get_groups_for_member(git, user)

                    def _match(group):
                        return group.path in [g.adname for g in groups]

                    def _remove(group):
                        return group.path not in [g.adname for g in groups]

                    def _add(group):
                        return group.adname not in [g.path for g in gitlab_groups]

                    # Filter lists to create add/remove lists
                    remove = list(filter(_remove, gitlab_groups))
                    add = list(filter(_add, groups))
                    matched = list(filter(_match, gitlab_groups))

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
                        gitlab_group = self.get_group(git, group.adname)
                        if fix:
                            if gitlab_group:
                                # noinspection PyUnresolvedReferences
                                gitlab_group.members.create({
                                    'user_id': user.id,
                                    'access_level': gitlab.DEVELOPER_ACCESS,
                                })
                            else:
                                logger.error("Could not find GitLab group {} with id {}!".format(group.name, group.id))

        if mp.is_group() and mp.extra_data().get('gitlab', False):
            logger.debug("Mapping is a group and should have a GitLab group, checking if the group exists in GitLab.")

            if mp.adname:
                # Check if committee has a group
                group = self.get_group(git, mp.adname)

                if group:
                    logger.debug("GitLab group for {} exists.".format(mp.adname))

                if group is None and mp.needs_account():
                    logger.debug("GitLab group for {} does not exist, creating.".format(mp.adname))
                    if fix:
                        group = git.groups.create({
                            'name': mp.name,
                            'path': mp.adname,
                        })
                        if group:
                            changes.append(('group', '{} created'.format(group.path)))
                            claudia.notify_gitlab_created(mp, mp.adname)
                        else:
                            logger.error("GitLab group creation for {} failed.".format(mp.adname))

        if changes:
            claudia.notify_gitlab_changed(mp, mp.adname, changes)

    @staticmethod
    def get_group(git, path):
        groups = git.groups.list(per_page=100)
        if groups is not None:
            for group in groups:
                if group.path == path:
                    return group
        return None

    @staticmethod
    def get_groups_for_member(git, user):
        groups = git.groups.list(per_page=100)
        res = []
        for group in groups:
            for member in group.members.list(per_page=100):
                if member.username == user.username:
                    res.append(group)
        return res

    @staticmethod
    def get_user(git, username):
        """
        Get the user information for a given username.

        Returns None if the user is not found.
        """
        users = git.users.list(username=username)
        if len(users) > 0:
            return users[0]

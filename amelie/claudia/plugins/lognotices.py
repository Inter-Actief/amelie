import logging

from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.tools import format_changes


logger = logging.getLogger(__name__)


class LogNoticesPlugin(ClaudiaPlugin):
    """
    Plugin to log notices from Claudia to plugins to the Claudia log.
    """

    def mapping_created(self, claudia, mp):
        logger.info('Mapping "%s" created.' % mp.name)

    def mapping_changed(self, claudia, mp, changes):
        logger.info('Mapping "%s" changed: %s' % (mp.name, format_changes(changes)))

    def mapping_deleted(self, claudia, mp):
        logger.info('Mapping "%s" deleted.' % mp.name)

    def account_created(self, claudia, mp, password):
        logger.info('Account "%s" of "%s" created' % (mp.adname, mp.name))

    def account_changed(self, claudia, mp, changes):
        logger.info('Account "%s" of "%s" changed: %s' % (mp.adname, mp.name, format_changes(changes)))

    def account_scheduled_delete(self, claudia, mp):
        logger.info('Account "%s" of "%s" delete scheduled.' % (mp.adname, mp.name))

    def account_unscheduled_delete(self, claudia, mp):
        logger.info('Account "%s" of "%s" delete unscheduled.' % (mp.adname, mp.name))

    def gsuite_created(self, cm, mp):
        logger.info('GSuite account of "{}" created'.format(mp.name))

    def gsuite_changed(self, cm, mp, changes):
        logger.info('GSuite account of "{}" changed: {}'.format(mp.name, format_changes(changes)))

    def gsuite_scheduled_delete(self, cm, mp):
        logger.info('GSuite account of "{}" delete scheduled.'.format(mp.name))

    def gsuite_unscheduled_delete(self, cm, mp):
        logger.info('GSuite account of "{}" delete unscheduled.'.format(mp.name))

    def alexia_created(self, claudia, mp, radius):
        logger.info('Alexia account "%s" of "%s" created' % (radius, mp.name))

    def alexia_changed(self, claudia, mp, radius, changes):
        logger.info('Alexia account "%s" of "%s" changed: %s' % (radius, mp.name, format_changes(changes)))

    def gitlab_created(self, claudia, mp, account):
        logger.info('GitLab account "%s" of "%s" created' % (account, mp.name))

    def gitlab_changed(self, claudia, mp, account, changes):
        logger.info('GitLab account "%s" of "%s" changed: %s' % (account, mp.name, format_changes(changes)))

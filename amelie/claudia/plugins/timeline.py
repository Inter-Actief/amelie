from amelie.claudia.models import Timeline
from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.tools import format_changes


class TimelinePlugin(ClaudiaPlugin):
    def mapping_created(self, claudia, mp):
        Timeline.create(mp.name, mp, 'CREATE MAPPING')

    def mapping_changed(self, claudia, mp, changes):
        Timeline.create(mp.name, mp, 'CHANGE MAPPING', format_changes(changes))

    def mapping_deleted(self, claudia, mp):
        Timeline.create(mp.name, mp, 'DELETE MAPPING')

    def account_created(self, claudia, mp, passwd):
        Timeline.create(mp.adname, mp, 'CREATE ACCOUNT')

    def account_changed(self, claudia, mp, changes):
        Timeline.create(mp.adname, mp, 'CHANGE ACCOUNT', format_changes(changes))

    def account_scheduled_delete(self, claudia, mp):
        Timeline.create(mp.adname, mp, 'DELETE ACCOUNT')

    def account_unscheduled_delete(self, claudia, mp):
        Timeline.create(mp.adname, mp, 'UNDELETE ACCOUNT')

    def kanidm_created(self, claudia, mp):
        Timeline.create(mp.name, mp, 'CREATE KANIDM')

    def kanidm_changed(self, claudia, mp, changes):
        Timeline.create(mp.name, mp, 'CHANGE KANIDM', format_changes(changes))

    def kanidm_deleted(self, claudia, mp):
        Timeline.create(mp.name, mp, 'DELETE KANIDM')

    def gsuite_created(self, claudia, mp):
        Timeline.create(mp.name, mp, 'CREATE GSUITE ACCOUNT')

    def gsuite_changed(self, claudia, mp, changes):
        Timeline.create(mp.name, mp, 'CHANGE GSUITE ACCOUNT', format_changes(changes))

    def gsuite_scheduled_delete(self, claudia, mp):
        Timeline.create(mp.name, mp, 'DELETE GSUITE ACCOUNT')

    def gsuite_unscheduled_delete(self, claudia, mp):
        Timeline.create(mp.name, mp, 'UNDELETE ACCOUNT')

    def alexia_created(self, claudia, mp, radius):
        Timeline.create(radius, mp, 'CREATE ALEXIA')

    def alexia_changed(self, claudia, mp, radius, changes):
        Timeline.create(radius, mp, 'CHANGE ALEXIA', format_changes(changes))

    def gitlab_created(self, claudia, mp, account):
        Timeline.create(account, mp, 'CREATE GITLAB')

    def gitlab_changed(self, claudia, mp, account, changes):
        Timeline.create(account, mp, 'CHANGE GITLAB', format_changes(changes))

    def matrix_created(self, claudia, mp, account):
        Timeline.create(account, mp, 'CREATE MATRIX')

    def matrix_changed(self, claudia, mp, account, changes):
        Timeline.create(account, mp, 'CHANGE MATRIX', format_changes(changes))

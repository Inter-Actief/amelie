"""Contains the ClaudiaPlugin base class."""


class ClaudiaPlugin(object):
    """
    Plugin to log notices from Claudia to plugins to the Claudia log.
    """

    def mapping_created(self, claudia, mp):
        """
        Signal that a mapping has been activated.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Activated mapping.
        """
        pass

    def mapping_changed(self, claudia, mp, changes):
        """
        Signal that a mapping has changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Changed mapping.
        :param changes: Changes.
        """
        pass

    def mapping_deleted(self, claudia, mp):
        """
        Signal that a mapping has been deactivated.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Deactivated mapping.
        """
        pass

    def account_created(self, claudia, mp, password):
        """
        Signals that an AD account has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param password: Password of the new account.
        """
        pass

    def account_changed(self, claudia, mp, changes):
        """
        Signals that the AD account has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param changes: Changes.
        """
        pass

    def account_scheduled_delete(self, claudia, mp):
        """
        Signals that the AD account has been scheduled for deletion.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def account_unscheduled_delete(self, claudia, mp):
        """
        Signals that the AD account has been unscheduled for deletion.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def kanidm_created(self, claudia, mp):
        """
        Signals that a Kanidm account has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def kanidm_changed(self, claudia, mp, changes):
        """
        Signals that a Kanidm account has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param changes: Changes.
        """
        pass

    def kanidm_deleted(self, claudia, mp):
        """
        Signals that a Kanidm account has been deleted.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def gsuite_created(self, claudia, mp):
        """
        Signals that a GSuite account has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def gsuite_changed(self, claudia, mp, changes):
        """
        Signals that a GSuite account has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param changes: Changes.
        """
        pass

    def gsuite_scheduled_delete(self, claudia, mp):
        """
        Signals that a GSuite account has been scheduled for deletion.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def gsuite_unscheduled_delete(self, claudia, mp):
        """
        Signals that a GSuite account has been unscheduled for deletion.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        """
        pass

    def alexia_created(self, claudia, mp, radius):
        """
        Signals that an Alexia account has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode radius: RADIUS username.
        """
        pass

    def alexia_changed(self, claudia, mp, radius, changes):
        """
        Signals that the Alexia account has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode radius: RADIUS username.
        :param changes: Changes.
        """
        pass

    def gitlab_created(self, claudia, mp, account):
        """
        Signals that an GitLab account has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode account: RADIUS username.
        """
        pass

    def gitlab_changed(self, claudia, mp, account, changes):
        """
        Signals that the GitLab account has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode account: RADIUS username.
        :param changes: Changes.
        """
        pass

    def matrix_created(self, claudia, mp, account):
        """
        Signals that a Matrix space has been created.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode account: RADIUS username.
        """
        pass

    def matrix_changed(self, claudia, mp, account, changes):
        """
        Signals that the Matrix space has been changed.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Related mapping.
        :param unicode account: RADIUS username.
        :param changes: Changes.
        """
        pass

    def verify_mapping(self, claudia, mp, fix=False):
        """
        Signals that a Mapping must be verified.

        :param Claudia claudia: The Claudia object.
        :param Mapping mp: Mapping to verify.
        :param bool fix: Fixes should be applied.
        """
        pass

    def verify_finished(self, claudia):
        """
        Signals that verification has been finished.

        :param Claudia claudia: The Claudia object.
        """
        pass

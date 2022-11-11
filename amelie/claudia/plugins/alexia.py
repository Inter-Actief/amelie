"""Claudia plugin for managing Alexia accounts, authorizations and RFID cards."""
import logging

from amelie.claudia.clau import Claudia
from amelie.claudia.models import Mapping
from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.personal_tab.alexia import get_alexia

logger = logging.getLogger(__name__)


class AlexiaPlugin(ClaudiaPlugin):
    """
    Alexia-plugin for Claudia

    Handles the synchronisation of data to Alexia

    Authors: j.zeilstra & k.alberts
    """

    @staticmethod
    def _get_accountname(mp):
        """
        Determine account name for Alexia.
        :param Mapping mp: Mapping
        :return: account name or None
        """
        extra_data = mp.extra_data()
        student_number = extra_data.get('student_number')
        employee_number = extra_data.get('employee_number')

        logger.debug("Student number: {}, employee number: {}".format(student_number, employee_number))

        if not student_number and not employee_number:
            logger.debug("No student or employee number.")
            result = None
        elif student_number and not employee_number:
            # Only student number
            result = student_number
        elif not student_number and employee_number:
            # Only employee number
            result = employee_number
        else:
            # Both student number and employee number
            # Check if Alexia account already exists
            server = get_alexia()
            student_exists = server.user.exists(radius_username=student_number)
            employee_exists = server.user.exists(radius_username=employee_number)

            logger.debug("Student account: {}, employee account: {}".format(student_exists, employee_exists))

            if student_exists and not employee_exists:
                # Only student account exists
                result = student_number
            elif not student_exists and employee_exists:
                # Only employee account exists
                result = employee_number
            elif student_exists and employee_exists:
                logger.error("Multiple Alexia accounts exist for {} (cid: {}).".format(mp.name, mp.id))
                result = None
            else:
                # No account exits, use employee number
                result = employee_number
        return result

    def verify_mapping(self, claudia, mp, fix=False):
        """
        Verify Alexia account of mapping

        :param Claudia claudia: Claudia object.
        :param Mapping mp: Mapping object to verify.
        :param bool fix: Fixes should be applied.
        """
        changes = []

        logger.debug("Verifying Alexia data of {} (cid: {})".format(mp.name, mp.id))

        if not fix:
            logger.debug("No changes will me made to internal attributes")

        extra_data = mp.extra_data()
        radius = self._get_accountname(mp)

        if not radius:
            logger.debug("No account name, skipping.")
            return

        logger.debug("RADIUS account: {}".format(radius))

        amelie_rfids = set(extra_data.get('rfids', []))
        logger.debug("Amelie RFIDs: {}".format(amelie_rfids))

        amelie_authorization = extra_data.get('consumption_mandate', False)
        logger.debug("Amelie authorization: {}".format(amelie_authorization))

        if amelie_authorization:
            # Needs Alexia account
            needs_alexia_account = True
        else:
            needs_alexia_account = False
            logger.debug("No Alexia account needed, clearing RFIDs and authorization")
            amelie_rfids = set()
            amelie_authorization = False

        server = get_alexia()

        if not server.user.exists(radius_username=radius):
            if not needs_alexia_account:
                logger.debug("No Alexia account and no account needed, skipping person.")
                return

            logger.debug("Creating Alexia account.")
            if fix:
                res = server.user.add(first_name=mp.givenname(),
                                      last_name=mp.surname(),
                                      email=mp.email,
                                      radius_username=radius)
                if res:
                    claudia.notify_alexia_created(mp, radius)
                else:
                    logger.error("Creating Alexia account {} failed.".format(radius))
                    return
        else:
            logger.debug("Alexia account {} exists.".format(radius))

        ## RFIDs ##

        alexia_rfids = set(rfid['identifier'] for rfid in server.rfid.list(radius_username=radius))
        logger.debug("Alexia RFIDs: {}".format(alexia_rfids))

        rfids_to_add = amelie_rfids - alexia_rfids
        rfids_to_remove = alexia_rfids - amelie_rfids

        logger.debug("RFIDs to add: {}".format(rfids_to_add))
        logger.debug("RFIDs to remove: {}".format(rfids_to_remove))

        for rfid in rfids_to_add:
            logger.debug("Adding RFID {}".format(rfid))
            if fix:
                server.rfid.add(radius_username=radius, identifier=rfid)
                logger.debug("Added RFID {}".format(rfid))

        for rfid in rfids_to_remove:
            logger.debug("Removing RFID {}".format(rfid))
            if fix:
                server.rfid.remove(radius_username=radius, identifier=rfid)
                logger.debug("Removed RFID {}".format(rfid))

        if len(rfids_to_add) > 0:
            changes.append(('rfids', ['+{} rfids'.format(len(rfids_to_add))]))
        if len(rfids_to_remove) > 0:
            changes.append(('rfids', ['-{} rfids'.format(len(rfids_to_remove))]))

        ## Authorizations ##

        alexia_authorizations_all = server.authorization.list(radius_username=radius)
        alexia_authorizations_active = [m for m in alexia_authorizations_all if not m['end_date']]
        alexia_authorization = bool(alexia_authorizations_active)
        logger.debug("Alexia authorization: {}".format(alexia_authorization))

        if amelie_authorization and not alexia_authorization:
            logger.debug("Adding authorization")
            if fix:
                server.authorization.add(radius_username=radius, account='')
                logger.debug("Added authorization")
                changes.append(('authorization', ['added']))

        removed_authorizations = []
        if not amelie_authorization and alexia_authorization:
            for authorization in alexia_authorizations_active:
                logger.debug("Removing authorization {}".format(authorization['id']))
                if fix:
                    server.authorization.end(radius_username=radius, authorization_id=authorization['id'])
                    logger.debug("Removed authorization {}".format(authorization['id']))
                removed_authorizations.append(authorization['id'])

        if len(removed_authorizations) > 0:
            changes.append(('authorizations', ['-{}'.format(a) for a in removed_authorizations]))

        if changes:
            claudia.notify_alexia_changed(mp, radius, changes)

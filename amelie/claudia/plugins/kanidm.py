"""Plugin for managing KaniDM accounts."""

import logging
from typing import List, Union

from django.conf import settings

from amelie.claudia.kanidm import KanidmAPI, KanidmObject, KanidmPerson, KanidmGroup
from amelie.claudia.models import Mapping
from amelie.claudia.plugins.plugin import ClaudiaPlugin

logger = logging.getLogger(__name__)


KANIDM_DEFAULT_PERSON_GROUPS = ["idm_all_persons", "idm_all_accounts"]


class KanidmPlugin(ClaudiaPlugin):
    """
    Kanidm Accounts plugin for Claudia

    Links Claudia objects with Kanidm accounts.

    Authors: k.alberts
    """

    def __init__(self):
        self.kanidm = KanidmAPI()

    # ====== Useraccount-related ====
    def create_account(self, mp) -> Union[KanidmObject, None]:
        """
        Create an account for a mapping
        :type mp: Mapping
        """
        if mp.is_group():
            account = self.kanidm.create_group(name=mp.adname, description=mp.name)
        elif mp.is_person():
            account = self.kanidm.create_person(name=mp.adname, display_name=mp.name)
        else:
            raise ValueError("Mapping is neither a person nor a group.")

        # Allow for account creation to fail. Kanidm will ensure error reporting in this case.
        if not account:
            return None

        # Save Kanidm ID to mapping
        mp.set_kanidm_id(account.uuid)
        mp.save()

        # Configure UNIX attributes
        if mp.is_person():
            account.update_posix(gid=20000 + mp.id, shell=settings.CLAUDIA_SHELLS[settings.CLAUDIA_SHELL_DEFAULT])
        elif mp.is_group():
            account.update_posix(gid=20000 + mp.id)

        return account

    # ====== Verify! ====

    def verify_mapping(self, claudia, mp, fix=False):
        """
        Verifies all standard attributes of a mapping.
        :param claudia: Claudia object
        :type claudia: Claudia
        :param mp: Mapping to verify
        :type mp: Mapping
        :param fix: If fixes should be applied
        :type fix: bool
        """
        changes = []

        logger.debug(f"Verifying Kanidm account of {mp.name} (cid: {mp.id})")
        if not fix:
            logger.debug("No changes will me made to internal attributes")

        account = self.kanidm.get_for_mapping(mp)

        # Remove the Kanidm ID from the mapping if we can't find an account for it.
        if account is None and mp.get_kanidm_id():
            logger.debug(f"Removing invalid guid for {mp.name}")
            if fix:
                mp.set_kanidm_id(None)
                mp.save()

        # If the user needs an account and does not have one, create one.
        if account is None and mp.needs_account() and mp.adname:
            logger.debug(f"Object {mp.name} had no account, creating account with name {mp.adname}.")

            if fix:
                account = self.create_account(mp)
                if account:
                    changes.append(('account', f'{account.name} created'))
                    claudia.notify_kanidm_created(mp)

        # If we do have an account, check if we should have one.
        if account is not None:
            delete_reason = None
            if not mp.needs_account():
                delete_reason = "is no longer active"
            elif not mp.adname:
                delete_reason = "no longer has an account name"

            if delete_reason is not None:
                if isinstance(account, KanidmPerson) or isinstance(account, KanidmGroup):
                    logger.debug(f"{account.object_type} {account.name} {delete_reason}, deleting account.")
                    changes.append(('account', f'{mp.adname} deleted'))
                    if fix:
                        account.delete()
                        account = None
                        mp.set_kanidm_id(None)
                        mp.save()
                        claudia.notify_kanidm_deleted(mp)
                else:
                    raise ValueError(f"Object {mp.name} (cid {mp.id}) is not a group, but not a person either?")

        # Check account details
        if account:
            # Check if the account name is correct, only change it if it does not become empty.
            # In that case, the account has to be deleted.
            if mp.adname and mp.adname.lower() != account.name:
                logger.debug(f"Account name changed to {mp.adname} (was: {account.name})")
                changes.append(('account', (account.name, mp.adname)))
                if fix:
                    account.update_name(str(mp.adname))

            # Check group memberships
            groups: List[Mapping] = [group for group in mp.groups('ad') if group.is_group_active() and group.adname]
            active: List[KanidmGroup] = [group for group in account.direct_member_of]

            def _match(adgroup: KanidmGroup):
                return adgroup.name in [g.adname.lower() for g in groups]

            def _remove(adgroup: KanidmGroup):
                return adgroup.name not in [g.adname.lower() for g in groups] and adgroup.name not in KANIDM_DEFAULT_PERSON_GROUPS

            def _add(group: Mapping):
                return group.adname.lower() not in [g.name for g in active]

            # Filter group memberships into to be added/removed and matched lists
            remove: List[KanidmGroup] = list(filter(_remove, active))
            add: List[Mapping] = list(filter(_add, groups))
            matched: List[KanidmGroup] = list(filter(_match, active))

            if len(matched) > 0:
                logger.debug(f"Matched groups: {matched}")
            if len(remove) > 0:
                changes.append(('groups', [f'-{adgroup.name}' for adgroup in remove]))
            if len(add) > 0:
                changes.append(('groups', [f'+{group.adname}' for group in add]))

            # Remove from groups
            for adgroup in remove:
                logger.debug(f"Should not be in group {adgroup.name}")
                if fix:
                    adgroup.remove_member(account)

            # Add to groups
            for group in add:
                logger.debug(f"Should be in group {group.adname}")
                if fix:
                    # Lookup group account
                    ad_group = self.kanidm.get_group(group.adname)

                    # Check if the group actually exists
                    if not ad_group:
                        logger.debug(f"Group {group.adname} does not exist yet, verifying group to create it...")
                        # Let Claudia create the group if it does not exist.
                        claudia.do_verify_mp(group)
                        ad_group = self.kanidm.get_group(group.adname)
                    if ad_group:
                        logger.debug(f"Adding {account.name} to group {ad_group.name}")
                        ad_group.add_member(account)
                    else:
                        logger.warning(f"For some reason the group '{group.adname}' still doesn't exist after verifying it!")

            # Check some more account details for people.
            if mp.is_person():
                # Check account display_name
                if mp.name and account.display_name != mp.name:
                    changes.append(('display_name', (account.display_name, mp.name)))
                    if fix:
                        account.update_display_name(str(mp.name))

                # Check unix shell
                shell = mp.extra_data().get('shell', settings.CLAUDIA_SHELL_DEFAULT)
                if shell not in settings.CLAUDIA_SHELLS:
                    shell = settings.CLAUDIA_SHELL_DEFAULT
                shellpath = settings.CLAUDIA_SHELLS[shell]

                if shellpath != account.loginshell:
                    changes.append(('shell', (account.loginshell, shellpath)))
                    if fix:
                        account.update_posix(shell=shellpath)

            # Check some more account details for groups.
            if mp.is_group():
                # Check description
                if mp.name and account.description != mp.name:
                    changes.append(('description', (account.description, mp.name)))
                    if fix:
                        account.update_description(str(mp.name))

        # Notify if there were changes
        if changes:
            claudia.notify_kanidm_changed(mp, changes)

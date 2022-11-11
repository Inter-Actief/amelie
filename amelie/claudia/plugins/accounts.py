"""Plugin for managing AD accounts."""
import datetime
import logging

from django.conf import settings
from django.utils import timezone

from amelie.claudia.ad import AD
from amelie.claudia.models import Event, Mapping
from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.tools import unify_mail

logger = logging.getLogger(__name__)

DELETE_USER = 'DELETE_USER'


class AccountsPlugin(ClaudiaPlugin):
    """
    Active Directory Accounts plugin for Claudia

    Links Claudia objects with Active Directory accounts.

    Authors: b.c.peschier, m.kooijman, j.zeilstra & k.alberts
    """

    def __init__(self):
        a = settings.CLAUDIA_AD
        self.ad = AD(a["LDAP"], a["HOST"], a["USER"], a["PASSWORD"], a["BASEDN"], a["PORT"])

    # ====== Useraccount-related ====
    def create_account(self, mp):
        """
        Create an account for a mapping
        :type mp: Mapping
        """
        if mp.is_group():
            account = self.ad.add_group(str(mp.adname), mp.is_committee())
        elif mp.is_person():
            account = self.ad.add_account(str(mp.adname))
        else:
            raise ValueError

        # Allow for account creation to fail. ad will ensure error reporting in this case.
        if account:
            if mp.is_group():
                account.update_gid(mp.id)
            elif mp.is_person():
                account.update_uid(mp.id)

            # update guid-data in mapping
            mp.set_guid(account.guid())
            mp.save()

        return account

    def create_password(self, account):
        """
        Create a random password for a given account
        :type account: ADAccount
        :return: The password that was set.
        """

        import random
        import string

        letters = string.ascii_lowercase
        passwd = []
        # Generate random characters
        for i in range(8):
            if random.randint(0, 2) == 2:
                passwd.append(str(random.randint(0, 9)))
            else:
                passwd.append(letters[random.randint(0, 25)])

        passwd = ''.join(passwd)

        # Set the password and make sure the user has to change it.
        if account is not None:
            account.set_password(passwd)
            account.enable()
            account.must_change_password()
        else:
            raise ValueError("account invalid")

        return passwd

    def schedule_delete(self, mp, account):
        """
        Schedule the account for deletion, if it was not marked already.
        :type mp: Mapping
        :type account: ADAccount
        """
        if self.delete_scheduled(mp):
            logger.debug("User already scheduled for delete")
        else:
            expiration = timezone.now() + datetime.timedelta(30)
            account.set_expiration(expiration)
            Event(type=DELETE_USER, mapping=mp, execute=expiration).save()
            return True

    def unschedule_delete(self, mp, account):
        """
        Unschedule the account for deletion
        :type mp: Mapping
        :type account: ADAccount
        """
        if self.delete_scheduled(mp):
            if account:
                account.unset_expiration()
            Event.objects.filter(type=DELETE_USER, mapping=mp).delete()
            return True

    def delete_scheduled(self, mp):
        """
        Check if user is scheduled for deletion.
        :type mp: Mapping
        """
        return Event.objects.filter(type=DELETE_USER, mapping=mp).exists()

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

        logger.debug("Verifying account of %s (cid: %s)" % (mp.name, mp.id))
        if not fix:
            logger.debug("No changes will me made to internal attributes")

        if mp.get_guid() is not None:
            if mp.is_person():
                account = self.ad.get_person_guid(mp.get_guid())
            elif mp.is_group():
                account = self.ad.get_group_guid(mp.get_guid())
            else:
                raise ValueError
        else:
            account = None

        if mp.is_person() and self.delete_scheduled(mp) and mp.needs_account() and mp.adname:
            logger.debug("User is active again, removing scheduled delete")
            if fix and self.unschedule_delete(mp, account):
                claudia.notify_account_unscheduled_delete(mp)

        # Remove the GUID from the mapping if we can't find an account for it.
        if account is None and mp.get_guid():
            logger.debug("Removing invalid guid for %s" % mp.name)
            if fix:
                mp.set_guid(None)
                mp.save()

        # If the user needs an account and does not have one, create one.
        if account is None and mp.needs_account() and mp.adname:
            logger.debug("Object %s had no account, creating account with name %s." % (mp.name, mp.adname))

            if fix:
                account = self.create_account(mp)
                if account:
                    changes.append(('account', '%s created' % (account.account_name())))
                    if mp.is_person():
                        passwd = self.create_password(account)
                    else:
                        passwd = None
                    claudia.notify_account_created(mp, passwd)

        # If we do have an account, check if we should have one.
        if account is not None:
            delete_reason = None
            if not mp.needs_account():
                delete_reason = "is no longer active"
            elif not mp.adname:
                delete_reason = "no longer has an account name"

            if delete_reason is not None:
                if mp.is_group():
                    # Delete groups right away
                    logger.debug("Group %s %s, deleting account." % (mp.name, delete_reason))
                    changes.append(('account', '%s deleted' % mp.adname))
                    if fix:
                        account.delete()
                        account = None
                        mp.set_guid(None)
                        mp.save()
                elif mp.is_person():
                    logger.debug("User %s %s, scheduling account deletion." % (mp.name, delete_reason))
                    # But schedule persons for later deletion
                    if fix and self.schedule_delete(mp, account):
                        claudia.notify_account_scheduled_delete(mp)
                else:
                    raise ValueError("Object %s (cid %s) is not a group, but not a person either?" % (mp.name, mp.id))

        # Check account details
        if account:
            # Check if the e-mail address is correct
            if mp.email:
                if mp.is_group():
                    email = mp.email
                else:
                    # Use accountname@inter-actief.net alias for users instead of real e-mail address
                    email = unify_mail(mp.adname)

                if account.mail() != email:
                    logger.debug("Mail changed to %s (was: %s)" % (email, account.mail()))
                    changes.append(("mail", (account.mail(), email)))
                    if fix:
                        account.set_mail(str(email))

            # Check if the account name is correct, only change it if it does not become empty.
            # In that case, the account has to be deleted, but maybe only after 30 days.
            if mp.adname and mp.adname != account.account_name():
                logger.debug("Account name changed to %s (was: %s)" % (mp.adname, account.account_name()))
                changes.append(('account', (account.account_name(), mp.adname)))
                if fix:
                    account.set_account_name(str(mp.adname))

            # Check group memberships
            groups = [group for group in mp.groups('ad') if group.is_group_active() and group.adname]
            active = account.groups()

            def _match(adgroup):
                return adgroup.account_name() in [g.adname for g in groups]

            def _remove(adgroup):
                return adgroup.account_name() not in [g.adname for g in groups]

            def _add(group):
                return group.adname not in [g.account_name() for g in active]

            # Filter group memberships into to be added/removed and matched lists
            remove = list(filter(_remove, active))
            add = list(filter(_add, groups))
            matched = list(filter(_match, active))

            if len(matched) > 0:
                logger.debug("Matched groups: %r" % matched)
            if len(remove) > 0:
                changes.append(('groups', ['-%s' % adgroup.account_name() for adgroup in remove]))
            if len(add) > 0:
                changes.append(('groups', ['+%s' % group.adname for group in add]))

            # Remove from groups
            for adgroup in remove:
                logger.debug("Should not be in group %s" % adgroup.account_name())
                if fix:
                    account.delete_group(adgroup)

            # Add to groups
            for group in add:
                logger.debug("Should be in group %s" % group.adname)
                if fix:
                    # Lookup group AD account
                    ad_group = self.ad.find_group(str(group.adname))

                    # Check if group actually exists
                    if not ad_group:
                        # Let Claudia create the group if it does not exist.
                        claudia.do_verify_mp(group)
                        ad_group = self.ad.find_group(str(group.adname))
                    if ad_group:
                        account.add_group(ad_group)
                    else:
                        logger.warning("For some reason the group %s still doesn't exist after verifying it!"
                                       % group.adname)

            # Check some more account details for people.
            if mp.is_person():
                # Check account CN
                if mp.name and account.name() != mp.name:
                    changes.append(('adname', (account.name(), mp.name)))
                    if fix:
                        account.rename(str(mp.name))

                # Check first name
                if mp.givenname() and account.givenname() != mp.givenname():
                    changes.append(('givenname', (account.givenname(), mp.givenname())))
                    if fix:
                        account.set_givenname(str(mp.givenname()))

                # Check last name
                if mp.surname() and account.surname() != mp.surname():
                    changes.append(('surname', (account.surname(), mp.surname())))
                    if fix:
                        account.set_surname(str(mp.surname()))

                # Check unix shell
                shell = mp.extra_data().get('shell', settings.CLAUDIA_SHELL_DEFAULT)
                if shell not in settings.CLAUDIA_SHELLS:
                    shell = settings.CLAUDIA_SHELL_DEFAULT
                shellpath = settings.CLAUDIA_SHELLS[shell]

                if shellpath != account.shell():
                    changes.append(('shell', (account.shell(), shellpath)))
                    if fix:
                        account.set_shell(shellpath)

            # Check some more account details for groups
            if mp.is_group():
                # Check account CN
                if mp.adname and account.name() != mp.adname:
                    changes.append(('adname', (account.name(), mp.adname)))
                    if fix:
                        account.rename(str(mp.adname))

        # Notify if there were changes
        if changes:
            claudia.notify_account_changed(mp, changes)

import datetime
import logging
from typing import List, Tuple, Iterable

import googleapiclient
from django.utils import timezone

from amelie.claudia.clau import Claudia
from amelie.claudia.google import GoogleSuiteAPI
from amelie.claudia.models import Mapping, Event, DrivePermission
from amelie.claudia.plugins.plugin import ClaudiaPlugin
from django.conf import settings

logger = logging.getLogger(__name__)

DELETE_GSUITE_USER = 'DELETE_GSUITE_USER'


class GoogleSuitePlugin(ClaudiaPlugin):
    def __init__(self):
        self.google = GoogleSuiteAPI()

    # ======= Deletion scheduling functions =======

    def schedule_delete(self, mp):
        """
        Schedule the account for deletion, if it was not marked already.
        :type mp: Mapping
        """
        if self.delete_scheduled(mp):
            logger.debug("User already scheduled for delete")
        else:
            expiration = timezone.now() + datetime.timedelta(30)
            Event(type=DELETE_GSUITE_USER, mapping=mp, execute=expiration).save()
            return True

    def unschedule_delete(self, mp):
        """
        Unschedule the account for deletion
        :type mp: Mapping
        """
        if self.delete_scheduled(mp):
            Event.objects.filter(type=DELETE_GSUITE_USER, mapping=mp).delete()
            return True

    def delete_scheduled(self, mp):
        """
        Check if user is scheduled for deletion.
        :type mp: Mapping
        """
        return Event.objects.filter(type=DELETE_GSUITE_USER, mapping=mp).exists()

    # ======= Claudia functions =======

    def verify_mapping(self, claudia: Claudia, mp: Mapping, fix: bool = False) -> None:
        changes = []

        logger.debug("Verifying google suite object {object_name} (cid: {cid})"
                     .format(object_name=mp.name, cid=mp.id))

        if not fix:
            logger.debug("No changes will be made to internal or external accounts.")

        # If mapping has gsuite id, get its account
        account_group_memberships = []
        if mp.get_gsuite_id() is not None:
            if mp.is_person():
                account = self.google.get_user(mp)
                account_group_memberships = self.google.get_group_memberships(mp)
            elif mp.is_group():
                account = self.google.get_group(mp)
            elif mp.is_contact():
                # Contacts only have a GSuite ID to be able to delete them from groups, they don't really have accounts.
                # This entry is only here to avoid hitting the nasty ValueError below.
                account = None
            elif mp.is_shareddrive():
                account = self.google.get_shared_drive(mp)
            else:
                raise ValueError("Mapping {} (cid {}) is not a group, but not a person either?".format(mp.name, mp.id))
        else:
            account = None

        # If mappging is person, a delete is scheduled, but they need an account and have a username and e-mail,
        # remove the scheduled deletion
        if mp.is_person() and self.delete_scheduled(mp) and mp.needs_gsuite_account():
            logger.debug("User is active again, removing scheduled delete")
            if fix and self.unschedule_delete(mp):
                claudia.notify_gsuite_unscheduled_delete(mp)

        # If we could not find an account, but the mapping had a gsuite id and it is not a contact, remove the gsuite id
        if account is None and mp.get_gsuite_id() and not account_group_memberships and not mp.is_contact():
            logger.debug("Removing invalid GSuite ID for {}".format(mp.name))
            if fix:
                mp.set_gsuite_id(None)

        # If the user needs an account and has a username and e-mail, but no account, create one.
        if account is None and mp.needs_gsuite_account():
            if mp.is_person():
                if mp.adname:

                    # Need to create acount but first check if person is in any groups by its emailaddress
                    # If it is, remove it from the groups and create the account. The group memberships will be
                    # fixed later by the verification process.
                    logger.debug("Want to create account for {}, but first need to check old group memberships.".format(mp.name))
                    current_group_memberships = self.google.get_group_memberships(mp)
                    if not current_group_memberships:
                        logger.debug("{} has no group memberships on their e-mail address".format(mp.name))
                    for membership in current_group_memberships:
                        logger.debug("Removing old membership of e-mail {} from group {} <{}>".format(
                            mp.email, membership['name'], membership['email']
                        ))
                        self.google.remove_group_member(mp, membership)

                    logger.debug("Object {} had no GSuite account, creating one with name {}.".format(mp.name, mp.adname))
                    if fix:
                        account = self.google.create_user(mp)
                        if account:
                            changes.append(('gsuite', 'User {} created'.format(account['primaryEmail'])))
                            claudia.notify_gsuite_created(mp)
                else:
                    logger.debug("Not creating GSuite account for {}, because the mapping has no adname.".format(mp))
            elif mp.is_group():
                if mp.email:
                    logger.debug("Object {} had no GSuite group, creating one with email {}.".format(mp.name, mp.email))
                    if fix:
                        account = self.google.create_group(mp)
                        if account:
                            changes.append(('gsuite', 'Group {} <{}> created'.format(account['name'], account['email'])))
                            claudia.notify_gsuite_created(mp)
                else:
                    logger.debug("Not creating GSuite group for {}, because the mapping has no e-mail address.".format(
                        mp
                    ))
            elif mp.is_contact():
                # Contacts don't need an account, they are just an e-mail address in GSuite
                # But we pass here so we don't run into the nasty ValueError below.
                pass
            elif mp.is_shareddrive():
                logger.debug("Object {} is a new shared drive, creating shared drive.".format(mp.name))
                if fix:
                    account = self.google.create_shared_drive(mp)
                    if account:
                        changes.append(('gsuite', 'Shared Drive {} created'.format(account['name'])))
                        claudia.notify_gsuite_created(mp)
            else:
                raise ValueError("Mapping {} (cid {}) is not a group, but not a person or contact either?".format(
                    mp.name, mp.id))

        # If the user has an account, check if we need one. If not, schedule deletion if person, and delete if group
        if account is not None:
            delete_reason = None
            if not mp.needs_gsuite_account():
                if mp.is_person() and not mp.adname:
                    delete_reason = "no longer has an account name"
                elif not mp.email:
                    delete_reason = "no longer has an e-mail address"
                else:
                    delete_reason = "is no longer active"

            if delete_reason is not None:
                if mp.is_group():
                    # Delete groups right away
                    logger.debug("Group {} {}, deleting GSuite group.".format(mp.name, delete_reason))
                    changes.append(('gsuite', 'Group {} deleted'.format(mp.name, mp.email)))
                    if fix:
                        self.google.delete_group(mp)
                        account = None
                        mp.set_gsuite_id(None)
                elif mp.is_person():
                    logger.debug("User {} {}, scheduling GSuite account deletion.".format(mp.name, delete_reason))
                    # Schedule persons for later deletion
                    if fix and self.schedule_delete(mp):
                        claudia.notify_gsuite_scheduled_delete(mp)
                else:
                    raise ValueError("Mapping {} (cid {}) is not a group, "
                                     "but not a person either?".format(mp.name, mp.id))

        # If we have an account or this is a contact or a person, check the details
        if account:
            # If it is a person, check the details for a User in GSuite
            if account and mp.is_person():
                changes += self.verify_mapping_person(claudia=claudia, mp=mp, account=account, fix=fix)

            # If it is a group, check the details for a Group in GSuite
            elif mp.is_group():
                changes += self.verify_mapping_group(claudia=claudia, mp=mp, account=account, fix=fix)

            # If it is a shared drive, check the name and permissions
            elif mp.is_shareddrive():
                changes += self.verify_mapping_shareddrive(claudia=claudia, mp=mp, account=account, fix=fix)

            # Else, wtf, what is this thing?
            else:
                raise ValueError("Mapping {} (cid {}) is not a group, but not a person either?".format(mp.name, mp.id))

        # Verify group memberships for anything that has an account, is a contact, or is a person (people can
        # be in groups without having an account (e.g. do-group aliases))
        if account or mp.is_contact() or mp.is_person():
            # If it has an account, or is a contact or person with an e-mail address
            if (account or ((mp.is_contact() or mp.is_person()) and mp.email)) and not mp.is_shareddrive():
                # Check if group memberships for the account are correct
                website_aliases = [g for g in mp.groups('mail') if g.is_gsuite_group_active() and g.email]
                website_aliases_emails = [x.email.lower() for x in website_aliases]
                gsuite_groups = self.google.get_group_memberships(mp)
                gsuite_group_emails = [x['email'].lower() for x in gsuite_groups]

                to_add_groups = [x for x in website_aliases if x.email not in gsuite_group_emails]
                to_remove_groups = [x for x in gsuite_groups if x['email'] not in website_aliases_emails]
                matched_groups = [x for x in website_aliases_emails if x in gsuite_group_emails]

                if matched_groups:
                    logger.debug("Matched groups: {}".format(matched_groups))
                if to_add_groups:
                    logger.debug("Should be added to GSuite groups: {}".format([x.email for x in to_add_groups]))
                    changes.append(('gsuite_groups', ["+{}".format(x.email) for x in to_add_groups]))
                if to_remove_groups:
                    logger.debug("Should be removed from GSuite groups: {}".format([x['email'] for x in to_remove_groups]))
                    changes.append(('gsuite_groups', ["-{}".format(x['email']) for x in to_remove_groups]))

                if to_add_groups or to_remove_groups:
                    if fix:
                        for group in to_add_groups:
                            # First check if this group actually exists
                            gs_group = self.google.get_group(group)
                            if not gs_group:
                                # Let Claudia verify the group if it does not exist
                                claudia.do_verify(group)
                                gs_group = self.google.get_group(group)

                            if gs_group:
                                details = self.google.add_group_member(mp, group)
                                # Contacts (and inactive people) are added by e-mail in a group,
                                # but cannot be deleted by e-mail.
                                # They can only be deleted by using the unique ID that they get when adding them, so
                                # we save that as the gsuite ID and use it when deleting it.
                                if details is not None and (mp.is_contact() or (mp.is_person() and not mp.gsuite_id)):
                                    mp.gsuite_id = details['id']
                                    mp.save()
                        for group in to_remove_groups:
                            self.google.remove_group_member(mp, group)

        # Notify if there were changes
        if changes:
            claudia.notify_gsuite_changed(mp, changes)

    def verify_mapping_person(self, claudia: Claudia, mp: Mapping, account, fix: bool = False) -> List[Tuple[str, Iterable[str]]]:
        changes = []

        logger.debug("Checking Person-specific details for {object_name} (cid: {cid})".format(
            object_name=mp.name, cid=mp.id
        ))

        # Check if e-mail address is correct (only if adname is present, or else it would result in an empty e-mail)
        if mp.adname:
            primary_alias = "{}@{}".format(mp.adname, settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])
            if account['primaryEmail'] != primary_alias:
                logger.debug("Mail changed to {} (was: {})".format(primary_alias, account['primaryEmail']))
                changes.append(("mail", (account['primaryEmail'], primary_alias)))
                if fix:
                    self.google.update_user_primary_email(mp)

        # Check if First and Last names are correct
        update = False
        if mp.givenname() and mp.surname():  # Needs to have both to be able to check them separately
            if account['name']['givenName'] != mp.givenname():
                logger.debug("Given name changed to {} (was: {})".format(mp.givenname(), account['name']['givenName']))
                update = True
                changes.append(("givenName", (account['name']['givenName'], mp.givenname())))
            if account['name']['familyName'] != mp.surname():
                logger.debug("Surname changed to {} (was: {})".format(mp.surname(), account['name']['familyName']))
                update = True
                changes.append(("familyName", (account['name']['familyName'], mp.surname())))
        else:
            if account['name']['givenName'] != mp.name or account['name']['familyName'] != mp.name:
                logger.debug("Name changed to {} (was: {})".format(mp.name, account['name']['givenName']))
                update = True
                changes.append(("name", (account['name']['givenName'], mp.name)))

        if update and fix:
            self.google.update_user_name(mp)

        # Check if personal aliases are correct (only if the adname is set)
        if mp.adname:
            # Remove adname from aliases because that is our primary email
            aliases = filter(lambda x: x != mp.adname, mp.personal_aliases())
            should_be_aliases = ["{}@{}".format(x, settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN']) for x in aliases]

            # Add extra personal aliases that were manually added to this mapping
            should_be_aliases += [x.email for x in mp.extra_personal_aliases.all()]

            # Add the aliases key into the account if it does not exist
            if 'aliases' not in account:
                account['aliases'] = []

            to_add_aliases = [x for x in should_be_aliases if x not in account['aliases']]
            to_remove_aliases = [x for x in account['aliases'] if x not in should_be_aliases]
            matched_aliases = [x for x in should_be_aliases if x in account['aliases']]

            if matched_aliases:
                logger.debug("Matched personal aliases: {}".format(matched_aliases))
            if to_add_aliases:
                logger.debug("Should be added to personal aliases: {}".format(to_add_aliases))
                changes.append(('personal_aliases', ["+{}".format(x) for x in to_add_aliases]))
            if to_remove_aliases:
                logger.debug("Should be removed from personal aliases: {}".format(to_remove_aliases))
                changes.append(('personal_aliases', ["-{}".format(x) for x in to_remove_aliases]))

            if to_add_aliases or to_remove_aliases:
                if fix:
                    self.google.update_personal_aliases(mp, to_add_aliases, to_remove_aliases)

        return changes

    def verify_mapping_group(self, claudia: Claudia, mp: Mapping, account, fix: bool = False) -> List[Tuple[str, Iterable[str]]]:
        changes = []

        logger.debug("Checking Group-specific details for {object_name} (cid: {cid})".format(
            object_name=mp.name, cid=mp.id
        ))

        # Check group e-mail address
        if account['email'] != mp.email:
            logger.debug("Mail changed to {} (was: {})".format(mp.email, account['email']))
            changes.append(("mail", (account['email'], mp.email)))
            if fix:
                self.google.update_group_email(mp)

        # Check group name
        if account['name'] != mp.name:
            logger.debug("Name changed to {} (was: {})".format(mp.name, account['name']))
            changes.append(("name", (account['name'], mp.name)))
            if fix:
                self.google.update_group_name(mp)

        # Check group description
        if 'description' in mp.extra_data():
            if account['description'] != mp.extra_data()['description']:
                logger.debug("Description changed to {} (was: {})".format(mp.extra_data()['description'],
                                                                          account['description']))
                changes.append(("description", (account['description'], mp.extra_data()['description'])))
                if fix:
                    self.google.update_group_description(mp)

        # Check group aliases
        should_be_aliases = [x.email for x in mp.extra_personal_aliases.all()]

        # Add the aliases key into the account if it does not exist
        if 'aliases' not in account:
            account['aliases'] = []

        to_add_aliases = [x for x in should_be_aliases if x not in account['aliases']]
        to_remove_aliases = [x for x in account['aliases'] if x not in should_be_aliases]
        matched_aliases = [x for x in should_be_aliases if x in account['aliases']]

        if matched_aliases:
            logger.debug("Matched personal aliases: {}".format(matched_aliases))
        if to_add_aliases:
            logger.debug("Should be added to personal aliases: {}".format(to_add_aliases))
            changes.append(('extra_aliases', ["+{}".format(x) for x in to_add_aliases]))
        if to_remove_aliases:
            logger.debug("Should be removed from personal aliases: {}".format(to_remove_aliases))
            changes.append(('extra_aliases', ["-{}".format(x) for x in to_remove_aliases]))

        if to_add_aliases or to_remove_aliases:
            if fix:
                self.google.update_group_aliases(mp, to_add_aliases, to_remove_aliases)

        # Check permissions of a group.
        email = settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL']
        gsettings_api = GoogleSuiteAPI.create_directory_service(
            user_email=email,
            api_name="groupssettings",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GROUPSSETTINGS_API']
        )

        # Get group to generate changes list
        group = None
        try:
            group = gsettings_api.groups().get(groupUniqueId=mp.email).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not get settings info for group {} - Message: {}".format(mp, e))

        default_settings = {
            "kind": "groupsSettings#groups",
            "whoCanJoin": "INVITED_CAN_JOIN",  # Only invited members may join
            "whoCanViewMembership": "ALL_MEMBERS_CAN_VIEW",  # Members can see the other members
            "whoCanViewGroup": "ALL_MEMBERS_CAN_VIEW",  # Members can see the messages in the group
            "whoCanModerateMembers": "NONE",  # No one may moderate members
            "allowExternalMembers": "false",  # No external members may view and join the group
            "whoCanPostMessage": "ANYONE_CAN_POST",  # Anyone may e-mail this group
            "allowWebPosting": "true",  # Posts via the web forum are allowed
            "isArchived": "true",  # Messages sent to this group are kept in an archive
            "archiveOnly": "false",  # This group is not inactive
            "messageModerationLevel": "MODERATE_NONE",  # Messages are not moderated, and sent directly to the group
            "spamModerationLevel": "MODERATE",  # Send detected spam messages to the moderation queue, but don't notify anyone
            "replyTo": "REPLY_TO_IGNORE",  # Users may decide where the message reply is sent
            "includeCustomFooter": "false",  # No custom footer on each message
            "sendMessageDenyNotification": "false",  # Do not send a notification to authors if their message was rejected
            "showInGroupDirectory": "false",  # Do not show this group in the groups directory
            "allowGoogleCommunication": "false",  # Google may not contact this group's administrators
            "membersCanPostAsTheGroup": "true",  # Members are allowed to send messages using the group's address
            "messageDisplayFont": "DEFAULT_FONT",  # Messages are shown using the default font
            "includeInGlobalAddressList": "true",  # This group is visible in the address book
            "whoCanLeaveGroup": "NONE_CAN_LEAVE",  # You cannot escape!
            "whoCanContactOwner": "ALL_MEMBERS_CAN_CONTACT",  # Members may contact the group owner (claudia)
            "whoCanModerateContent": "ALL_MEMBERS",  # All members may moderate content (e.g. manage spam)
            "whoCanAssistContent": "ALL_MEMBERS",  # All members may manage content assistant controls
        }

        if group:
            diff = {x: (group[x] if x in group.keys() else "", default_settings[x])
                    for x in default_settings.keys() if x not in group.keys() or group[x] != default_settings[x]}

            if len(diff) != 0:
                for x, y in diff.items():
                    changes.append(("group_settings_{}".format(x), y))

                try:
                    gsettings_api.groups().patch(
                        groupUniqueId=mp.email,
                        body=default_settings
                    ).execute()
                except googleapiclient.errors.HttpError as e:
                    logger.warning("Unable to update group settings for {} - Message: {}".format(mp, e))

        return changes

    def verify_mapping_shareddrive(self, claudia: Claudia, mp: Mapping, account, fix: bool = False) -> List[Tuple[str, Iterable[str]]]:
        changes = []

        logger.debug("Checking Shared Drive-specific details for {object_name} (cid: {cid})".format(
            object_name=mp.name, cid=mp.id
        ))

        # Check Shared Drive name
        if account['name'] != mp.name:
            logger.debug("Name changed to {} (was: {})".format(mp.name, account['name']))
            changes.append(("name", (account['name'], mp.name)))
            if fix:
                self.google.update_shared_drive(mp)

        # Get all mappings that should be in the drive
        should_be_in = mp.members()

        # Get all mappings that are currently in the drive
        currently_in = self.google.get_drive_permissions(mp)
        currently_in_ids = [x['id'] for x in currently_in['permissions']]
        currently_in_permissions = DrivePermission.objects.filter(drive=mp.get_mapped_object(),
                                                                  permission_id__in=currently_in_ids)
        missing_ids = [x for x in currently_in_ids if x not in [y.permission_id for y in currently_in_permissions]]
        currently_in_mappings = [x.mapping for x in currently_in_permissions]

        to_add_mappings = [x for x in should_be_in if x not in currently_in_mappings]
        to_remove_mappings = [x for x in currently_in_mappings if x not in should_be_in]
        matched_mappings = [x for x in should_be_in if x in currently_in_mappings]

        to_remove_ids = [
            x for x in missing_ids if not self.google.get_drive_permission(drive=mp, id=x)['emailAddress']
                                          == settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL']
        ]

        if matched_mappings:
            logger.debug("Matched mappings of shared drives: {}".format(matched_mappings))
        if to_add_mappings:
            logger.debug("Should be added to shared drive: {}".format(to_add_mappings))
            changes.append(('shared_drive', ["+{}".format(x) for x in to_add_mappings]))
            if fix:
                for x in to_add_mappings:
                    self.google.create_drive_permission(mp, x)
        if to_remove_mappings:
            logger.debug("Should be removed from shared drive: {}".format(to_remove_mappings))
            changes.append(('shared_drive', ["-{}".format(x) for x in to_remove_mappings]))
            if fix:
                for x in to_remove_mappings:
                    self.google.delete_drive_permission(mp, x)
        if to_remove_ids:
            logger.debug("Should be removed from shared drive: {}".format(to_remove_ids))
            changes.append(('shared_drive', ["-{}".format(x) for x in to_remove_ids]))
            if fix:
                for x in to_remove_ids:
                    self.google.delete_drive_permission_by_id(mp, x)

        return changes


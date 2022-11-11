import logging
import uuid

import googleapiclient
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

from amelie.claudia.models import Mapping, DrivePermission
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleSuiteAPI:
    def __init__(self):
        self.api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="admin",
            api_version="directory_v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DOMAIN_API']
        )

    @staticmethod
    def create_directory_service(user_email, api_name, api_version, scopes):
        credentials = ServiceAccountCredentials.from_p12_keyfile(
            settings.CLAUDIA_GSUITE['SERVICE_ACCOUNT_EMAIL'],
            settings.CLAUDIA_GSUITE['SERVICE_ACCOUNT_P12_FILE'],
            'notasecret',
            scopes=scopes
        )
        credentials = credentials.create_delegated(user_email)
        return build(api_name, api_version, credentials=credentials)

    # noinspection PyMethodMayBeStatic
    def create_password(self):
        """
        Create a random password
        :return: The sha1 hash of the password.
        """
        import random
        import string
        import hashlib

        letters = string.ascii_lowercase
        passwd = []

        # Generate random characters
        for i in range(16):
            if random.randint(0, 2) == 2:
                passwd.append(str(random.randint(0, 9)))
            else:
                passwd.append(letters[random.randint(0, 25)])

        passwd = "".join(passwd)
        passwd_hash = hashlib.sha1(passwd.encode("utf-8")).hexdigest()
        return passwd_hash

    def get_user(self, mp: Mapping):
        try:
            return self.api.users().get(userKey=mp.gsuite_id, projection='full', viewType='admin_view').execute()
        except googleapiclient.errors.HttpError:
            return None

    def create_user(self, mp: Mapping):
        users = self.api.users()

        primary_alias = "{}@{}".format(mp.adname, settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])
        password = self.create_password()

        try:
            if mp.givenname() and mp.surname():
                name = {
                    "givenName": mp.givenname(),  # First Name
                    "familyName": mp.surname(),  # Last Name
                }
            else:
                name = {
                    "givenName": mp.name,  # First Name
                    "familyName": mp.name,  # Last Name
                }

            # Template from:
            # https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/admin_directory_v1.users.html#insert
            user_details = users.insert(body={
                "suspended": False,
                "includeInGlobalAddressList": True,
                "orgUnitPath": "/",
                "primaryEmail": primary_alias,
                # Random password, no need to know it because logins are via SAML
                "password": password,
                "hashFunction": "SHA-1",
                "emails": [{
                    "address": primary_alias,
                    "primary": True,
                    "type": "work",
                    "customType": "",
                }],
                "kind": "admin#directory#user",
                "name": name,
                "changePasswordAtNextLogin": False,
            }).execute()

            # Save the new user ID in the mapping
            mp.set_gsuite_id(user_details['id'])

            return user_details
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not create GSuite user for {} - Message: {}".format(mp, e))

    def update_user_primary_email(self, mp: Mapping):
        users = self.api.users()
        primary_alias = "{}@{}".format(mp.adname, settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])
        try:
            users.patch(userKey=mp.gsuite_id, body={'primaryEmail': primary_alias}).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not update primary email for user {} - Message: {}".format(mp, e))

    def update_user_name(self, mp: Mapping):
        users = self.api.users()
        try:
            if mp.givenname() and mp.surname():
                name = {
                    "givenName": mp.givenname(),  # First Name
                    "familyName": mp.surname(),  # Last Name
                }
            else:
                name = {
                    "givenName": mp.name,  # First Name
                    "familyName": mp.name,  # Last Name
                }
            users.patch(userKey=mp.gsuite_id, body={'name': name}).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not update name for {} - Message: {}".format(mp, e))

    def update_personal_aliases(self, mp, to_add_aliases, to_remove_aliases):
        aliases = self.api.users().aliases()

        for to_remove in to_remove_aliases:
            try:
                aliases.delete(userKey=mp.gsuite_id, alias=to_remove).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not remove personal alias {} for {} - Message: {}".format(to_remove, mp, e))
        for to_add in to_add_aliases:
            try:
                # Template from:
                # https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/admin_directory_v1.users.aliases.html#insert
                aliases.insert(userKey=mp.gsuite_id, body={
                    "alias": to_add,  # A alias email
                    "kind": "admin#directory#alias",  # Kind of resource this is.
                }).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not add personal alias {} for {} - Message: {}".format(to_add, mp, e))

    def update_group_aliases(self, mp, to_add_aliases, to_remove_aliases):
        aliases = self.api.groups().aliases()

        for to_remove in to_remove_aliases:
            try:
                aliases.delete(groupKey=mp.gsuite_id, alias=to_remove).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not remove group alias {} for {} - Message: {}".format(to_remove, mp, e))
        for to_add in to_add_aliases:
            try:
                # Template from:
                # https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/admin_directory_v1.users.aliases.html#insert
                aliases.insert(groupKey=mp.gsuite_id, body={
                    "alias": to_add,  # A alias email
                    "kind": "admin#directory#alias",  # Kind of resource this is.
                }).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not add group alias {} for {} - Message: {}".format(to_add, mp, e))

    def get_group(self, mp: Mapping):
        if mp.gsuite_id:
            try:
                return self.api.groups().get(groupKey=mp.gsuite_id).execute()
            except googleapiclient.errors.HttpError:
                return None
        else:
            return None

    def create_group(self, mp: Mapping):
        groups = self.api.groups()

        extra_data = mp.extra_data()
        description = extra_data['description'] if 'description' in extra_data else ""
        name = mp.name
        email = mp.email.replace("inter-actief.net",
                                 settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])  # TODO: Temporary replace <-

        try:
            # Template from:
            # https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/admin_directory_v1.groups.html#insert
            group_details = groups.insert(body={
                "kind": "admin#directory#group",
                "description": description,
                "name": name,
                "email": email,  # Email of Group
            }).execute()

            # Save the new group ID in the mapping
            mp.set_gsuite_id(group_details['id'])

            return group_details
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not create GSuite group for {} - Message: {}".format(mp, e))

    def update_group_email(self, group: Mapping):
        users = self.api.groups()

        email = group.email.replace("inter-actief.net",
                                    settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])  # TODO: Temporary replace <-

        try:
            users.patch(groupKey=group.gsuite_id, body={'email': email}).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not update email for group {} - Message: {}".format(group, e))

    def update_group_name(self, group: Mapping):
        users = self.api.groups()
        try:
            users.patch(groupKey=group.gsuite_id, body={'name': group.name}).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not update name for group {} - Message: {}".format(group, e))

    def update_group_description(self, group: Mapping):
        if 'description' in group.extra_data():
            users = self.api.groups()
            try:
                users.patch(groupKey=group.gsuite_id, body={'description': group.extra_data()['description']}).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not update description for group {} - Message: {}".format(group, e))
        else:
            logger.debug("Not updating description for group {} - This mapping type has no description.".format(group))

    def get_group_members(self, group: Mapping):
        members = self.api.members()

        members_list = []

        try:
            # Get the initial members list
            members_request = members.list(groupKey=group.gsuite_id)
            members_data = members_request.execute()
            if 'members' in members_data:
                members_list.extend(members_data['members'][:])
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not get group members for group {} - Message: {}".format(group, e))
            return []

        # Retrieve next page(s) until there are none left, and add those members as well.
        while members_data:
            try:
                members_request = members.list_next(previous_request=members_request, previous_response=members_data)
                if members_request:
                    members_data = members_request.execute()
                else:
                    members_data = None
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not get next page of group members for group {} - Message: {}".format(group, e))

            if members_data and 'members' in members_data:
                members_list.extend(members_data['members'][:])

        return members_list

    def get_group_memberships(self, member: Mapping):
        groups = self.api.groups()
        try:
            # People that are active and have their own GSuite account
            if member.is_person() and member.gsuite_id:
                res = groups.list(userKey=member.gsuite_id).execute()
            # People that are not active (and should be added by e-mail address)
            elif member.is_person() and member.email:
                res = groups.list(userKey=member.email).execute()
            # Contacts that should be identified by their unique id or e-mail address
            elif member.is_contact() and member.gsuite_id:
                # Contacts are really strange in groups. Because they are basically just an e-mail address which is
                # added to a group. If it is just a normal e-mail address, it can be found using its GSuite ID, which is
                # unique to that address and is the same in all groups that it is in.
                # If, however, the e-mail address is ALSO a GSuite group (possibly in a DIFFERENT DOMAIN(!) from ours),
                # then it cannot be accessed using its GSuite ID, but needs to be managed by e-mail address.
                # Google will throw an error 400 - Invalid input: memberKey. So we will just try to get the info using
                # the GSuite ID, and if 400's, we assume it's secretly a GSuite group and retrieve it with the e-mail.
                # - albertskja, 2018-12-18
                try:
                    res = groups.list(userKey=member.gsuite_id).execute()
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status == 400 and "Invalid Input: memberKey".lower() in str(e).lower():
                        # This e-mail address is probably also a GSuite group in a different domain. Lookup by e-mail
                        res = groups.list(userKey=member.email).execute()
                    else:
                        raise e

            # Other things that only have an e-mail address
            elif member.email:
                res = groups.list(userKey=member.email).execute()

            # Unknown stuff
            else:
                logger.warning("I don't quite know what the group memberships of {} <mid: {}> are.".format(member,
                                                                                                           member.id))
                return []

            if 'groups' in res:
                return res['groups']
            else:
                return []
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not get group memberships for user {} <{}> - Message: {}".format(member,
                                                                                                   member.email, e))
            return []

    def add_group_member(self, member: Mapping, group: Mapping):
        members = self.api.members()

        try:
            # Template from:
            # https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/admin_directory_v1.members.html#insert

            # Active people should be added by their GSuite ID
            if member.is_person() and member.gsuite_id and member.needs_gsuite_account():
                member_details = members.insert(groupKey=group.gsuite_id, body={
                    "id": member.gsuite_id,
                    "kind": "admin#directory#member",
                    "role": "MEMBER",
                }).execute()

            # Inactive people who should be added by their e-mail address
            elif member.is_person() and member.email and not member.needs_gsuite_account():
                member_details = members.insert(groupKey=group.gsuite_id, body={
                    "email": member.email,
                    "kind": "admin#directory#member",
                    "role": "MEMBER",
                }).execute()

            # Other things that are not people
            elif not member.is_person():
                member_details = members.insert(groupKey=group.gsuite_id, body={
                    "email": member.email,
                    "kind": "admin#directory#member",
                    "role": "MEMBER",
                }).execute()
            else:
                logger.warning("Could not add person {} to group {} <{}> - Person either needs a GSuite account "
                               "but does not have one, or does not have an e-mail address.".format(member, group,
                                                                                                   group.email))
                return None

            return member_details
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not add member {} <{}> to group {} <{}> (#{}) - Message: {}".format(
                member, member.email, group.name, group.email, group.gsuite_id, e
            ))

    def remove_group_member(self, member: Mapping, group: dict):
        try:
            # Active people who have their own gsuite account
            if member.is_person() and member.gsuite_id:
                self.api.members().delete(groupKey=group['id'], memberKey=member.gsuite_id).execute()
            # Inactive people who are in groups with their e-mail address
            elif member.is_person() and member.email:
                self.api.members().delete(groupKey=group['id'], memberKey=member.email).execute()

            # Contacts
            elif member.is_contact():
                if member.gsuite_id:
                    try:
                        self.api.members().delete(groupKey=group['id'], memberKey=member.gsuite_id).execute()
                    except googleapiclient.errors.HttpError as e:
                        if e.resp.status == 400 and "Invalid Input: memberKey".lower() in str(e).lower():
                            # This address is probably also a GSuite group in a different domain. Remove by e-mail
                            self.api.members().delete(groupKey=group['id'], memberKey=member.email).execute()
                        else:
                            raise e
                else:
                    logging.warning("Could not delete contact {} from group {} <{}>, "
                                    "because the contact did not have a GSuite ID. "
                                    "Please check this manually.".format(member, group['name'], group['email']))

            # Other stuff
            else:
                self.api.members().delete(groupKey=group['id'], memberKey=member.email).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not delete member {} from group {} <{}> (#{}) - Message: {}".format(
                member, group['name'], group['email'], group['id'], e
            ))

    def delete_user(self, mp: Mapping):
        try:
            self.api.users().delete(userKey=mp.gsuite_id).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not delete user {} (#{}) - Message: {}".format(mp, mp.gsuite_id, e))

    def delete_group(self, mp: Mapping):
        try:
            self.api.groups().delete(groupKey=mp.gsuite_id).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not delete group {} (#{}) - Message: {}".format(mp, mp.gsuite_id, e))

    def make_user_admin(self, mp: Mapping):
        try:
            self.api.users().makeAdmin(userKey=mp.gsuite_id, body={
                "status": True
            }).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not promote admin status for user {} (#{}) - Message: {}".format(mp, mp.gsuite_id, e))

    def make_user_not_admin(self, mp: Mapping):
        try:
            self.api.users().makeAdmin(userKey=mp.gsuite_id, body={
                "status": False
            }).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not demote admin status for user {} (#{}) - Message: {}".format(mp, mp.gsuite_id, e))

    def add_user_forwarding_address(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            gmail_api.users().settings().forwardingAddresses().create(
                userId=user_mail,
                body={'forwardingEmail': mp.email}
            ).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not add forwarding address {} for user {} - Message: {}".format(mp.email, mp, e))

    def remove_user_forwarding_address(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            gmail_api.users().settings().forwardingAddresses().delete(
                userId=user_mail,
                forwardingEmail=mp.email
            ).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not remove forwarding address {} for user {} - Message: {}".format(mp.email, mp, e))

    def get_user_forwarding_addresses(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            res = gmail_api.users().settings().forwardingAddresses().list(userId=user_mail).execute()
            if 'forwardingAddresses' in res:
                return {x['forwardingEmail']: x['verificationStatus'] for x in res['forwardingAddresses']}
            else:
                return {}
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not get forwarding addresses for user {} - Message: {}".format(mp, e))

        return {}

    def get_user_forwarding_enabled(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            res = gmail_api.users().settings().getAutoForwarding(
                userId=user_mail
            ).execute()
            if 'enabled' in res:
                return {
                    "enabled": res['enabled'],
                    "emailAddress": res['emailAddress']
                }
            else:
                return {}
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not get forwarding information for user {} - Message: {}".format(mp, e))

        return {}

    def set_user_enable_forwarding(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            # Template from:
            # https://developers.google.com/resources/api-libraries/documentation/gmail/v1/python/latest/gmail_v1.users.settings.html#updateAutoForwarding
            body = {
                'enabled': True,
                'emailAddress': mp.email,
                'disposition': "archive",
            }
            gmail_api.users().settings().updateAutoForwarding(
                userId=user_mail,
                body=body
            ).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not enable forwarding to address {} for user {} - Message: {}".format(
                mp.email, mp, e
            ))

    def set_user_disable_forwarding(self, mp: Mapping):
        user_mail = self.get_user(mp)['primaryEmail']

        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=user_mail,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        try:
            # Template from:
            # https://developers.google.com/resources/api-libraries/documentation/gmail/v1/python/latest/gmail_v1.users.settings.html#updateAutoForwarding
            body = {
                'enabled': False,
            }
            gmail_api.users().settings().updateAutoForwarding(
                userId=user_mail,
                body=body
            ).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not disable forwarding to address {} for user {} - Message: {}".format(
                mp.email, mp, e
            ))

    def create_shared_drive(self, mp: Mapping):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        request_id = str(uuid.uuid4())
        metadata = {"name": mp.get_drivename(),
                    "restrictions": {
                        "adminManagedRestrictions": True,
                        "copyRequiresWriterPermission": False,
                        "domainUsersOnly": False,
                        "driveMembersOnly": True,
                    },
                    "colorRgb": "1d428a"}
        try:
            drive = drive_api.drives().create(body=metadata, requestId=request_id).execute()
            mp.set_gsuite_id(drive['id'])
            return drive
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not create shared drive for {} ({}). Message: {}".format(mp.get_drivename(), mp, e))

    def update_shared_drive(self, mp: Mapping):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        metadata = {"name": mp.get_drivename()}
        try:
            drive = drive_api.drives().update(driveId=mp.get_gsuite_id(), body=metadata).execute()
            mp.set_gsuite_id(drive['id'])
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not update shared drive for {} ({}). Message: {}".format(mp.get_drivename(), mp, e))

    def get_shared_drive(self, mp: Mapping):
        if mp.gsuite_id:
            drive_api = GoogleSuiteAPI.create_directory_service(
                user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
                api_name="drive",
                api_version="v3",
                scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
            )
            try:
                return drive_api.drives().get(driveId=mp.get_gsuite_id()).execute()
            except googleapiclient.errors.HttpError as e:
                logger.warning("Could not get shared drive for {} ({}). Message: {}".format(mp.get_drivename(), mp, e))
        return None

    def create_drive_permission(self, drive: Mapping, member: Mapping):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )

        if member.is_person() and member.gsuite_id and member.needs_gsuite_account():
            email = "{}@{}".format(member.adname, settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])
        else:
            email = member.email
        metadata = {"emailAddress": email,
                    "role": "fileOrganizer",
                    "type": "group" if member.is_group() else "user",
                    }
        try:
            res = drive_api.permissions().create(fileId=drive.get_gsuite_id(), body=metadata,
                                                   sendNotificationEmail=False, supportsAllDrives=True,
                                                   useDomainAdminAccess=True).execute()
            DrivePermission.objects.create(drive=drive.get_mapped_object(), mapping=member, permission_id=res['id'])
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not create permission for {} for user {}. Message: {}".format(drive, member, e))

    def delete_drive_permission(self, drive: Mapping, member: Mapping):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        permission_id = DrivePermission.objects.get(drive=drive.get_mapped_object(), mapping=member)

        try:
            drive_api.permissions().delete(fileId=drive.get_gsuite_id(), permissionId=permission_id.permission_id,
                                           supportsAllDrives=True, useDomainAdminAccess=True).execute()
            permission_id.delete()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not delete permission for {} for user {}. Message: {}".format(drive, member, e))

    def delete_drive_permission_by_id(self, drive: Mapping, id: str):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        try:
            permission_id = DrivePermission.objects.get(drive=drive.get_mapped_object(), permission_id=id)
        except DrivePermission.DoesNotExist:
            permission_id = None

        try:
            drive_api.permissions().delete(fileId=drive.get_gsuite_id(), permissionId=id,
                                           supportsAllDrives=True, useDomainAdminAccess=True).execute()
            if permission_id is not None:
                permission_id.delete()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not delete permission for {} by ID for ID {}. Message: {}".format(drive, id, e))

    def get_drive_permission(self, drive: Mapping, id: str):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        try:
            return drive_api.permissions().get(fileId=drive.get_gsuite_id(), permissionId=id,
                                               fields="emailAddress",
                                               supportsAllDrives=True, useDomainAdminAccess=True).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not retrieve permission ID {} for drive {}. Message: {}".format(id, drive, e))

    def get_drive_permissions(self, drive: Mapping):
        drive_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.CLAUDIA_GSUITE['DOMAIN_ADMIN_ACCOUNT_EMAIL'],
            api_name="drive",
            api_version="v3",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['DRIVE_API']
        )
        try:
            return drive_api.permissions().list(fileId=drive.get_gsuite_id(), pageSize=100,
                                                supportsAllDrives=True, useDomainAdminAccess=True).execute()
        except googleapiclient.errors.HttpError as e:
            logger.warning("Could not retrieve permissions for {}. Message: {}".format(drive, e))

import datetime
import json
import re
import time
import uuid
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.utils.translation import gettext as _

from amelie.iamailer import MailTask
from amelie.members.models import Person
from amelie.tools.keycloak import KeycloakAPI
from amelie.tools.mail import PersonRecipient


class IAOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    def verify_claims(self, claims):
        """Block login if the OIDC claims do not give a value for a username we support"""
        # IA username
        has_ia_username = claims.get('iaUsername', None) is not None
        # UT Student number
        has_student_number = claims.get('studentNumber', None) is not None
        # UT Employee number
        has_employee_number = claims.get('employeeNumber', None) is not None
        # UT X-account username
        has_ut_xaccount = claims.get('externalUsername', None) is not None
        # Keycloak local username
        has_local_username = claims.get('localUsername', None) is not None

        can_continue = has_ia_username or has_student_number or has_employee_number or \
            has_ut_xaccount or has_local_username
        self.log.debug(f"User login claims verification can continue: {can_continue}, with claims: {claims}")
        if not can_continue:
            # Person doesn't exist and should not be logged in, inform the user
            messages.error(self.request, _(
                "You were successfully logged in, but we could not verify your identity. "
                "This might be the case if your login session has expired. "
                "Please <a href='{logout_url}' target='_blank'>click here</a> to log out completely and try again."
            ).format(logout_url=settings.OIDC_LOGOUT_URL))
        return can_continue

    def _get_or_create_user(self, username, person=None):
        if person:
            # Get or create the user object for this person
            user, created = person.get_or_create_user(username)
        else:
            # Get or create the user object for this unknown user (possibly not linked to a Person)
            user, created = User.objects.get_or_create(username=username)
        return user, created

    def filter_users_by_claims(self, claims):
        # IA username
        ia_username = claims.get('iaUsername', None)
        ia_username = ia_username.lower() if ia_username else None
        # UT Student number
        student_username = claims.get('studentNumber', None)
        student_username = student_username.lower() if student_username else None
        # UT Employee number
        employee_username = claims.get('employeeNumber', None)
        employee_username = employee_username.lower() if employee_username else None
        # UT X-account username
        ut_xaccount = claims.get('externalUsername', None)
        ut_xaccount = ut_xaccount.lower() if ut_xaccount else None
        # OIDC Preferred username as a last resort
        local_username = claims.get('localUsername', None)
        local_username = local_username.lower() if local_username else None

        # Try to find Person by IA account name
        if ia_username is not None:
            self.log.debug(f"Trying login with IA Username {ia_username}...")
            # Block login if in list of disallowed users
            if not settings.DEBUG and ia_username in settings.LOGIN_NOT_ALLOWED_USERNAMES:
                self.log.info(f"User login for {ia_username} blocked because username is in the list of disallowed users.")
                return self.UserModel.objects.none()
            try:
                person = Person.objects.get(account_name=ia_username)
                user, created = self._get_or_create_user(ia_username, person)
                self.log.info(f"User login to {'new' if created else 'existing'} user {user.username} with IA username {ia_username}, Person {person} allowed.")
                return [user]
            except Person.DoesNotExist:
                pass

        # Try to find person by Student number
        if student_username is not None:
            self.log.debug(f"Trying login with student username {student_username}...")
            s_number = int(student_username[1:])
            try:
                person = Person.objects.get(student__number=s_number)
                user, created = self._get_or_create_user(student_username, person)
                self.log.info(f"User login to {'new' if created else 'existing'} user {user.username} with S-number {student_username}, Person {person} allowed.")
                return [user]
            except Person.DoesNotExist:
                pass

        # Try to find person by Employee number
        if employee_username is not None:
            self.log.debug(f"Trying login with employee username {employee_username}...")
            m_number = int(employee_username[1:])
            try:
                person = Person.objects.get(employee__number=m_number)
                user, created = self._get_or_create_user(employee_username, person)
                self.log.info(f"User login to {'new' if created else 'existing'} user {user.username} with M-number {employee_username}, Person {person} allowed.")
                return [user]
            except Person.DoesNotExist:
                pass

        # Try to find person by X-account username
        if ut_xaccount is not None:
            self.log.debug(f"Trying login with X-username {ut_xaccount}...")
            try:
                person = Person.objects.get(ut_external_username=ut_xaccount)
                user, created = self._get_or_create_user(ut_xaccount, person)
                self.log.info(f"User login to {'new' if created else 'existing'} user {user.username} with X-number {ut_xaccount}, Person {person} allowed.")
                return [user]
            except Person.DoesNotExist:
                pass

        # Try to find a user based on local username
        if local_username is not None:
            self.log.debug(f"Trying login with local username {local_username}...")
            match = re.match(r'ia(?P<person_id>[0-9]+)', local_username)
            if match:
                person_id = int(match.group('person_id'))
                try:
                    person = Person.objects.get(pk=person_id)
                    user, created = self._get_or_create_user(local_username, person)
                    self.log.info(f"User login to {'new' if created else 'existing'} user {user.username} with local username {local_username}, Person {person} allowed.")
                    return [user]
                except Person.DoesNotExist:
                    pass

        # No cigar.
        messages.error(
            self.request, _(
                "You were successfully logged in, but no account could be found. This might be "
                "the case if you aren't a member yet, or aren't a member anymore. "
                "If you want to become a member you can contact the board."
            ))
        self.log.info(f"User login failed, no username found to match against.")
        return self.UserModel.objects.none()


def get_oauth_link_code(person):
    # Get keycloak API
    kc = KeycloakAPI()

    # See if a Keycloak user already exists
    users = kc.get_user_details_by_username(username=f"ia{person.pk}")
    user = users[0] if users and len(users) > 0 else None
    three_days_from_now = round(time.mktime((datetime.datetime.now() + datetime.timedelta(days=3)).timetuple()))
    link_code = str(uuid.uuid4())

    if user is None:
        # Create user
        last_name = f"{person.last_name_prefix} {person.last_name}" if person.last_name_prefix else person.last_name

        try:
            kc.create_user(username=f"ia{person.pk}", first_name=person.first_name, last_name=last_name,
                           attributes={
                               "created_by": "amelie", "localUsername": f"ia{person.pk}",
                               "link_code": link_code,
                               "link_code_valid": f"{three_days_from_now}"
                           })
        except ConnectionError as e:
            raise ConnectionError(f"Error creating KeyCloak user ia{person.pk} - {e}")
    else:
        # Generate new link code for user
        new_attributes = user['attributes']
        new_attributes["link_code"] = link_code
        new_attributes["link_code_valid"] = f"{three_days_from_now}"
        try:
            kc.update_user(user_id=user['id'], data={
                "attributes": new_attributes
            })
        except ConnectionError as e:
            raise ConnectionError(f"Error updating KeyCloak user ia{person.pk} - {e}")
    return link_code


def send_oauth_link_code_email(request, person, link_code):
    task = MailTask(template_name="send_oauth_link_code.mail",
                    report_to=request.person.email_address,
                    report_always=False)
    task.add_recipient(PersonRecipient(
        recipient=person,
        context={"link_code": link_code}
    ))
    task.send()


def get_user_info(person):
    # Get keycloak API
    kc = KeycloakAPI()

    # Find all users associated with the current user
    all_users = []
    possible_usernames = [f"ia{person.pk}"]
    if person.account_name:
        possible_usernames.append(person.account_name)
    if person.is_student() and person.student.student_number():
        possible_usernames.append(person.student.student_number())
    if person.is_employee() and person.employee.employee_number():
        possible_usernames.append(person.employee.employee_number())
    if person.ut_external_username:
        possible_usernames.append(person.ut_external_username)

    for username in possible_usernames:
        users = kc.get_brief_user_details_by_username(username=username)
        if users and len(users) > 0:
            user_data = kc.get_user_details_by_user_id(user_id=users[0]['id'])
            user_data['credentials'] = kc.get_user_credentials_by_user_id(user_id=users[0]['id'])
            all_users.append(user_data)

    return all_users


def unlink_totp(user_id, totp_id):
    # Delete TOTP in Keycloak
    KeycloakAPI().delete_credential(user_id=user_id, credential_id=totp_id)


def unlink_acount(user_id, provider_name):
    # Delete TOTP in Keycloak
    KeycloakAPI().delete_federated_identity(user_id=user_id, provider_name=provider_name)


def unlink_passkey(user_id, passkey_id):
    # Delete Passkey in KeyCloak
    KeycloakAPI().delete_credential(user_id=user_id, credential_id=passkey_id)


def register_totp(user_id):
    # Trigger OTP reset action in KeyCloak
    KeycloakAPI().register_totp(user_id=user_id)


def register_passkey(user_id):
    # Trigger passkey reset action in KeyCloak
    KeycloakAPI().register_passkey(user_id=user_id)


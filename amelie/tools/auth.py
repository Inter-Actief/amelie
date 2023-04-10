import datetime
import json
import time
import uuid

import requests
from django.conf import settings
from django.contrib.auth.models import User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from amelie.iamailer import MailTask
from amelie.members.models import Person
from amelie.tools.mail import PersonRecipient


class IAOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        """Block login if the OIDC claims do not give a value for a username we support"""
        verified = super(IAOIDCAuthenticationBackend, self).verify_claims(claims)

        print(claims)

        # IA username
        has_ia_username = claims.get('iaUsername', None) is not None
        # UT Student number
        has_student_number = claims.get('studentNumber', None) is not None
        # UT Employee number
        has_employee_number = claims.get('employeeNumber', None) is not None
        # UT X-account username
        has_ut_xaccount = claims.get('externalUsername', None) is not None
        # OIDC Preferred username
        has_preferred_username = claims.get('preferred_username', None) is not None

        return verified and (has_ia_username or has_student_number or has_employee_number or
                             has_ut_xaccount or has_preferred_username)

    def _get_or_create_user(self, username, person=None):
        if person:
            # Get or create the user object for this person
            user, created = person.get_or_create_user(username)
        else:
            # Get or create the user object for this unknown user (possibly not linked to a Person)
            user, created = User.objects.get_or_create(username=username)
        return user

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
        preferred_username = claims.get('preferred_username', None)
        preferred_username = preferred_username.lower() if preferred_username else None

        # Try to find Person by IA account name
        if ia_username is not None:
            # Block login if in list of disallowed users
            if not settings.DEBUG and ia_username in settings.LOGIN_NOT_ALLOWED_USERNAMES:
                return self.UserModel.objects.none()
            try:
                return [self._get_or_create_user(ia_username, Person.objects.get(account_name=ia_username))]
            except Person.DoesNotExist:
                pass

        # Try to find person by Student number
        if student_username is not None:
            s_number = int(student_username[1:])
            try:
                return [self._get_or_create_user(student_username, Person.objects.get(student__number=s_number))]
            except Person.DoesNotExist:
                pass

        # Try to find person by Employee number
        if employee_username is not None:
            m_number = int(employee_username[1:])
            try:
                return [self._get_or_create_user(employee_username, Person.objects.get(employee__number=m_number))]
            except Person.DoesNotExist:
                pass

        # Try to find person by X-account username
        if ut_xaccount is not None:
            try:
                return [self._get_or_create_user(ut_xaccount, Person.objects.get(ut_external_username=ut_xaccount))]
            except Person.DoesNotExist:
                pass

        # Try to find a user based on OIDC preferred_username, as a last ditch effort
        if preferred_username is not None:
            return [self._get_or_create_user(preferred_username)]

        # No cigar.
        return self.UserModel.objects.none()


def get_oauth_link_code(person):
    # Login to keycloak API
    response = requests.post(
        f"{settings.KEYCLOAK_API_AUTHN_ENDPOINT}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "client_id": settings.KEYCLOAK_API_CLIENT_ID, "client_secret": settings.KEYCLOAK_API_CLIENT_SECRET}
    )
    access_token = response.json()['access_token']

    # See if a Keycloak user already exists
    response = requests.get(
        f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/users?username=ia{person.pk}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    users = response.json()
    user = users[0] if len(users) > 0 else None
    three_days_from_now = round(time.mktime((datetime.datetime.now() + datetime.timedelta(days=3)).timetuple()))
    link_code = str(uuid.uuid4())

    if user is None:
        # Create user
        last_name = f"{person.last_name_prefix} {person.last_name}" if person.last_name_prefix else person.last_name
        response = requests.post(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/users",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            data=json.dumps({
                "username": f"ia{person.pk}", "firstName": person.first_name, "lastName": last_name,
                "emailVerified": True, "enabled": True, "attributes": {
                    "created_by": "amelie", "link_code": link_code,
                    "link_code_valid": f"{three_days_from_now}"
                }
            })
        )
        if response.status_code != 201:  # 201 is user created
            raise ValueError(f"Error creating KeyCloak user ia{person.pk} - {response.status_code} {response.content}")
    else:
        # Generate new link code for user
        new_attributes = user['attributes']
        new_attributes["link_code"] = link_code
        new_attributes["link_code_valid"] = f"{three_days_from_now}"
        response = requests.put(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/users/{user['id']}",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            data=json.dumps({
                "attributes": new_attributes
            })
        )
        if response.status_code != 204:  # 204 is no content (user updated successfully)
            raise ValueError(f"Error updating KeyCloak user ia{person.pk} - {response.status_code} {response.content}")
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

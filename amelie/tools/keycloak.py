import logging
import requests
import json

from django.conf import settings


class KeycloakAPI:
    def __init__(self):
        self.authn_endpoint = settings.KEYCLOAK_API_AUTHN_ENDPOINT
        self.client_id = settings.KEYCLOAK_API_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_API_CLIENT_SECRET
        self._access_token = None
        self.log = logging.getLogger(self.__class__.__name__)

    def login(self):
        response = requests.post(
            f"{self.authn_endpoint}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "client_id": self.client_id,
                  "client_secret": self.client_secret}
        )
        try:
            self._access_token = response.json()['access_token']
        except (json.JSONDecodeError, KeyError) as e:
            self.log.exception(f"Could not login to Keycloak API - "
                               f"status={response.status_code} content={response.content}")
            raise ConnectionError(f"Could not login to Keycloak API, see logs for details - "
                                  f"status={response.status_code}")

    @staticmethod
    def _get_content(response):
        if response.content:
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.content
        else:
            return None

    def get(self, path, success_codes=None):
        if self._access_token is None:
            self.login()

        if success_codes is None:
            success_codes = [200, 201, 204]

        response = requests.get(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/{path}",
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code in success_codes:
            return self._get_content(response)
        else:
            self.log.exception(f"Error calling GET on Keycloak API\n"
                               f"status={response.status_code} path={path}\n"
                               f"content={response.content}")
            raise ConnectionError(f"Error calling GET on Keycloak API, see logs for details - "
                                  f"status={response.status_code} path={path}")

    def post(self, path, data=None, success_codes=None):
        if self._access_token is None:
            self.login()

        if data is None:
            data = {}

        if success_codes is None:
            success_codes = [200, 201, 204]

        response = requests.post(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/{path}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}"
            },
            data=json.dumps(data)
        )
        if response.status_code in success_codes:
            return self._get_content(response)
        else:
            self.log.exception(f"Error calling POST on Keycloak API\n"
                               f"status={response.status_code} path={path}\n"
                               f"content={response.content}")
            raise ConnectionError(f"Error calling POST on Keycloak API, see logs for details - "
                                  f"status={response.status_code} path={path}")

    def put(self, path, data=None, success_codes=None):
        if self._access_token is None:
            self.login()

        if data is None:
            data = {}

        if success_codes is None:
            success_codes = [200, 201, 204]

        response = requests.put(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/{path}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}"
            },
            data=json.dumps(data)
        )
        if response.status_code in success_codes:
            return self._get_content(response)
        else:
            self.log.exception(f"Error calling PUT on Keycloak API\n"
                               f"status={response.status_code} path={path}\n"
                               f"content={response.content}")
            raise ConnectionError(f"Error calling PUT on Keycloak API, see logs for details - "
                                  f"status={response.status_code} path={path}")

    def delete(self, path, success_codes=None):
        if self._access_token is None:
            self.login()

        if success_codes is None:
            success_codes = [200, 201, 204]

        response = requests.delete(
            f"{settings.KEYCLOAK_API_BASE}/{settings.KEYCLOAK_REALM_NAME}/{path}",
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code in success_codes:
            return self._get_content(response)
        else:
            self.log.exception(f"Error calling DELETE on Keycloak API\n"
                               f"status={response.status_code} path={path}\n"
                               f"content={response.content}")
            raise ConnectionError(f"Error calling DELETE on Keycloak API, see logs for details - "
                                  f"status={response.status_code} path={path}")

    def get_user_details_by_username(self, username):
        return self.get(f"users?exact=true&username={username}")

    def create_user(self, username, first_name, last_name, attributes=None):
        if attributes is None:
            attributes = {}
        data = {
            "username": username, "firstName": first_name, "lastName": last_name,
            "emailVerified": True, "enabled": True, "attributes": attributes
        }
        return self.post("users", data=data)

    def update_user(self, user_id, data=None):
        if data is None:
            data = {}
        return self.put(f"users/{user_id}", data=data)

    def get_brief_user_details_by_username(self, username):
        return self.get(f"users?exact=true&briefRepresentation=true&username={username}")

    def get_user_details_by_user_id(self, user_id):
        return self.get(f"users/{user_id}")

    def get_user_credentials_by_user_id(self, user_id):
        return self.get(f"users/{user_id}/credentials")

    def delete_credential(self, user_id, credential_id):
        return self.delete(f"users/{user_id}/credentials/{credential_id}")

    def delete_federated_identity(self, user_id, provider_name):
        if provider_name in settings.KEYCLOAK_PROVIDERS_UNLINK_ALLOWED:
            return self.delete(f"users/{user_id}/federated-identity/{provider_name}")
        else:
            raise PermissionError(f"Cannot unlink {provider_name} via the website, contact the System Administrators.")

    def register_totp(self, user_id):
        return self.put(
            f"users/{user_id}/execute-actions-email?lifespan=43200",  # Lifespan means the register link is valid for 12h (43200 seconds)
            data=["CONFIGURE_TOTP"]
        )

    def register_passkey(self, user_id):
        return self.put(
            f"users/{user_id}/execute-actions-email?lifespan=43200",  # Lifespan means the register link is valid for 12h (43200 seconds)
            data=["webauthn-register-passwordless"]
        )


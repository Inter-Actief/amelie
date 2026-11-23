import requests

from amelie.settings import CLAUDIA_FORGEJO

def add_ssh_key(username: str, tag: str, key: str) -> bool:
    try:
        base_url = CLAUDIA_FORGEJO["API_BASE"]
        headers = {"Authorization": f"Bearer {CLAUDIA_FORGEJO['API_TOKEN']}"}

        current_keys = requests.get(f"{base_url}/users/{username}/keys", headers=headers).json()
        for current_key in current_keys:
            if current_key["key"] == key:
                return True

        requests.post(f"{base_url}/admin/users/{username}/keys", json={"key": key, "title": f"Imported from the Inter-Actief website: '{tag}'"})
        return True
    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)

        return False

import json
import logging
from functools import cached_property
from typing import Dict, Any, Union, List, Optional

import requests
from django.urls import reverse
from requests import RequestException

from amelie.claudia.models import Mapping
from django.conf import settings

logger = logging.getLogger(__name__)


class KanidmAPI:
    def __init__(self):
        self.config = settings.CLAUDIA_KANIDM
        self._connection_obj = None
        if 'API_BASE' not in self.config or not self.config['API_BASE']:
            logger.error("Missing Kanidm 'API_BASE' value in CLAUDIA_KANIDM config variable")
            raise AttributeError("Missing Kanidm 'API_BASE' config")
        if 'API_TOKEN' not in self.config or not self.config['API_TOKEN']:
            logger.error("Missing Kanidm 'API_TOKEN' value in CLAUDIA_KANIDM config variable")
            raise AttributeError("Missing Kanidm 'API_TOKEN' config")

    @property
    def _connection(self):
        if not self._connection_obj:
            self._connection_obj = requests.Session()
            self._connection_obj.headers.update({"Authorization": f'Bearer {self.config.get("API_TOKEN", "no-api-token")}'})
        return self._connection_obj

    def _get(self, path, params=None) -> Optional[Union[List[Any], Dict[str, Any]]]:
        resp = self._connection.get(f'https://{self.config["API_BASE"]}/{path}', params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, data=None) -> Optional[Union[List[Any], Dict[str, Any]]]:
        resp = self._connection.post(f'https://{self.config["API_BASE"]}/{path}', json=data)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path, data=None) -> Optional[Union[List[Any], Dict[str, Any]]]:
        resp = self._connection.put(f'https://{self.config["API_BASE"]}/{path}', json=data)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path, data=None) -> Optional[Union[List[Any], Dict[str, Any]]]:
        resp = self._connection.patch(f'https://{self.config["API_BASE"]}/{path}', json=data)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path, data=None) -> Optional[Union[List[Any], Dict[str, Any]]]:
        resp = self._connection.delete(f'https://{self.config["API_BASE"]}/{path}', json=data)
        resp.raise_for_status()
        return resp.json()

    def get_object_from_spn(self, spn: str) -> 'KanidmObject':
        person = self.get_person(spn)
        if person:
            return person
        group = self.get_group(spn)
        if group:
            return group
        service_account = self.get_service_account(spn)
        if service_account:
            return service_account
        return KanidmUnknown(kanidm=self, attrs={'spn': spn})

    # ====== Kanidm API methods ==========
    def list_unwrapped_persons(self) -> List[Dict[str, Any]]:
        return self._get(f"v1/person")

    def list_persons(self) -> List['KanidmPerson']:
        return [KanidmPerson.from_json(kanidm=self, json_data=g) for g in self.list_unwrapped_persons()]

    def get_unwrapped_person(self, uuid_or_username: str) -> Dict[str, Any]:
        return self._get(f"v1/person/{uuid_or_username}")

    def get_person(self, uuid_or_username: str) -> 'KanidmPerson':
        return KanidmPerson.from_json(kanidm=self, json_data=self.get_unwrapped_person(uuid_or_username))

    def create_person(self, name: str, display_name: str) -> 'KanidmPerson':
        self._post("v1/person", data={"attrs": {"name": [name], "displayname": [display_name]}})
        # If no error occurred, the person should be created, and we can retrieve it.
        return self.get_person(name)

    def set_person_name(self, uuid_or_username: str, name: str):
        return self._patch(f"v1/person/{uuid_or_username}", data={"attrs": {"name": [name]}})

    def set_person_display_name(self, uuid_or_username: str, display_name: str):
        return self._patch(f"v1/person/{uuid_or_username}", data={"attrs": {"displayname": [display_name]}})

    def set_person_posix(self, uuid_or_username: str, gid: Optional[int] = None, shell: Optional[str] = None):
        data = {}
        if gid is not None:
            data["gidnumber"] = gid
        if shell is not None:
            data["shell"] = shell
        if data:
            return self._post(f"v1/person/{uuid_or_username}/_unix", data=data)
        return None

    def set_person_posix_password(self, uuid_or_username: str, password: str):
        return self._put(f"v1/person/{uuid_or_username}/_unix/_credential", data={"value": password})

    def list_person_ssh_pubkeys(self, uuid_or_username: str) -> List[Dict[str, str]]:
        # Only the /scim/ endpoint gives us the tag information...
        scim_data = self._get(f"scim/v1/Person/{uuid_or_username}?attributes=ssh_publickey")
        keys = scim_data.get("ssh_publickey", [])
        return keys  # [{"label": "key tag", "value": "ssh-ed25519 ...."}]

    def add_person_ssh_pubkeys(self, uuid_or_username: str, tag: str, pubkey: str):
        return self._post(f"v1/person/{uuid_or_username}/_ssh_pubkeys", data=[tag, pubkey])

    def delete_person_ssh_pubkeys(self, uuid_or_username: str, tag: str):
        return self._delete(f"v1/person/{uuid_or_username}/_ssh_pubkeys/{tag}")

    def delete_person(self, uuid_or_username: str):
        return self._delete(f"v1/person/{uuid_or_username}")

    def list_unwrapped_groups(self) -> List[Dict[str, Any]]:
        return self._get(f"v1/group")

    def list_groups(self) -> List['KanidmGroup']:
        return [KanidmGroup.from_json(kanidm=self, json_data=g) for g in self.list_unwrapped_groups()]

    def get_unwrapped_group(self, uuid_or_groupname: str) -> Dict[str, Any]:
        return self._get(f"v1/group/{uuid_or_groupname}")

    def get_group(self, uuid_or_groupname: str) -> 'KanidmGroup':
        return KanidmGroup.from_json(kanidm=self, json_data=self.get_unwrapped_group(uuid_or_groupname))

    def create_group(self, name: str, description: Optional[str] = None) -> 'KanidmGroup':
        group_attrs = {"name": [name]}
        if description:
            group_attrs["description"] = [description]
        self._post("v1/group", data={"attrs": group_attrs})
        # If no error occurred, the person should be created, and we can retrieve it.
        return self.get_group(name)

    def set_group_name(self, uuid_or_groupname: str, name: str):
        return self._patch(f"v1/group/{uuid_or_groupname}", data={"attrs": {"name": name}})

    def set_group_description(self, uuid_or_groupname: str, description: str):
        return self._patch(f"v1/group/{uuid_or_groupname}", data={"attrs": {"description": [description]}})

    def set_group_posix(self, uuid_or_groupname: str, gid: int):
        return self._post(f"v1/group/{uuid_or_groupname}/_unix", data={"gidnumber": gid})

    def add_member_to_group(self, group_uuid_or_groupname: str, member_uuid_username_groupname: str):
        return self._post(f"v1/group/{group_uuid_or_groupname}/_attr/member", data=[member_uuid_username_groupname])

    def remove_member_from_group(self, group_uuid_or_groupname: str, member_uuid_username_groupname: str):
        return self._delete(f"v1/group/{group_uuid_or_groupname}/_attr/member", data=[member_uuid_username_groupname])

    def delete_group(self, uuid_or_groupname: str):
        return self._delete(f"v1/group/{uuid_or_groupname}")

    def list_unwrapped_service_accounts(self) -> List[Dict[str, Any]]:
        return self._get(f"v1/service_account")

    def list_service_accounts(self) -> List['KanidmServiceAccount']:
        return [KanidmServiceAccount.from_json(kanidm=self, json_data=g) for g in self.list_unwrapped_service_accounts()]

    def get_unwrapped_service_account(self, uuid_or_username: str) -> Dict[str, Any]:
        return self._get(f"v1/service_account/{uuid_or_username}")

    def get_service_account(self, uuid_or_username: str) -> 'KanidmServiceAccount':
        return KanidmServiceAccount.from_json(kanidm=self, json_data=self.get_unwrapped_service_account(uuid_or_username))


    # ====== Claudia plugin helper methods =========
    def get_for_mapping(self, mp: Mapping) -> Optional['KanidmObject']:
        if not mp.get_kanidm_id():
            return None

        if mp.is_person():
            return self.get_person(mp.get_kanidm_id())
        elif mp.is_group():
            return self.get_group(mp.get_kanidm_id())
        else:
            raise ValueError(f"Cannot get Kanidm type for mapping: {mp}")

    def get_user_for_mapping(self, mp: Mapping) -> Optional['KanidmPerson']:
        if not mp.is_person():
            return None
        return self.get_for_mapping(mp)

    def get_group_for_mapping(self, mp: Mapping) -> Optional['KanidmGroup']:
        if not mp.is_group():
            return None
        return self.get_for_mapping(mp)


class KanidmObject:
    detail_url_name = None
    required_attrs = ["spn", "name", "uuid", "classes"]
    singular_attrs = ["spn", "name", "uuid", "display_name", "description", "gid", "loginshell"]
    attr_name_mapping = {
        "class": "classes",
        "displayname": "display_name",
        "gidnumber": "gid",
        "memberof": "member_of_strs",
        "directmemberof": "direct_member_of_strs",
        "member": "members_strs",
    }

    def __init__(self, kanidm: KanidmAPI, attrs: Dict[str, Any] = None):
        if self.__class__ == KanidmObject:
            raise TypeError("Cannot instantiate base class KanidmObject.")
        if kanidm is None:
            raise ValueError("Missing kanidm reference.")
        if attrs is None:
            attrs = {}

        self.kanidm: KanidmAPI = kanidm

        self.spn, self.name, self.uuid, self.classes = None, None, None, []

        self.attrs: Dict[str, Any] = attrs
        for attr, value in attrs.items():
            if self.attr_name_mapping.get(attr, attr) in self.singular_attrs:
                value = self.l2s(value)
            setattr(self, self.attr_name_mapping.get(attr, attr), value)

        missing_attrs = [attr for attr in self.required_attrs if (not hasattr(self, attr)) or getattr(self, attr) is None]
        if missing_attrs:
            raise ValueError(f"Missing required attributes: {missing_attrs}.")

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name})"

    def get_absolute_url(self) -> Optional[str]:
        if self.detail_url_name:
            return reverse(self.detail_url_name, kwargs={"uuid": self.uuid})
        return "#"

    @property
    def object_type(self):
        return self.__class__.__name__

    @property
    def is_system(self):
        return self.uuid.startswith("00000000-0000-0000-0000-")

    @staticmethod
    def l2s(l: Optional[List[str]]) -> Optional[str]:
        """Convert a single-entry JSON list to a string value."""
        if l is None or len(l) == 0:
            return None
        if len(l) == 1:
            return l[0]
        raise ValueError("Expected a single-entry list.")

    @classmethod
    def from_json(cls, kanidm: KanidmAPI, json_data: Dict[str, Any]) -> Optional['KanidmObject']:
        if json_data is None:
            return None
        return cls(kanidm=kanidm, attrs=json_data.get("attrs", {}))

    @property
    def attrs_str(self) -> str:
        return json.dumps(self.attrs, indent=2)

    @cached_property
    def claudia_mapping(self) -> Optional[Mapping]:
        try:
            return Mapping.objects.get(kanidm_id=self.uuid)
        except Mapping.DoesNotExist:
            return None


class KanidmUnknown(KanidmObject):
    required_attrs = ["spn"]  # We don't know what this is, so we only have the SPN
    def __str__(self):
        return f"[!] {self.spn}"


class KanidmPerson(KanidmObject):
    detail_url_name = "claudia:kanidm_person_detail"
    required_attrs = ["spn", "name", "uuid", "classes", "member_of_strs", "direct_member_of_strs"]

    def __init__(self, kanidm: KanidmAPI, attrs: Dict[str, Any] = None):
        self.display_name, self.gid, self.loginshell, self.member_of_strs, self.direct_member_of_strs = None, None, None, [], []
        super().__init__(kanidm=kanidm, attrs=attrs)

    def __str__(self):
        return f"{self.display_name or self.name}"

    @cached_property
    def member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.member_of_strs]

    @cached_property
    def direct_member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.direct_member_of_strs]

    def delete(self) -> bool:
        try:
            self.kanidm.delete_person(self.uuid)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_name(self, name: str) -> bool:
        try:
            self.kanidm.set_person_name(self.uuid, name=name)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_display_name(self, display_name: str) -> bool:
        try:
            self.kanidm.set_person_display_name(self.uuid, display_name=display_name)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_posix(self, gid: Optional[int] = None, shell: Optional[str] = None) -> bool:
        try:
            self.kanidm.set_person_posix(self.uuid, gid=gid, shell=shell)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def reset_posix_password(self) -> Optional[str]:
        from amelie.claudia.tools import create_password
        new_password = create_password(length=32)
        try:
            self.kanidm.set_person_posix_password(self.uuid, password=new_password)
            return new_password
        except RequestException as e:
            logger.error(e)
            return None

    def list_ssh_pubkeys(self) -> List[Dict[str, str]]:
        return self.kanidm.list_person_ssh_pubkeys(self.uuid)

    def add_ssh_pubkey(self, tag: str, pubkey: str) -> bool:
        try:
            self.kanidm.add_person_ssh_pubkeys(self.uuid, tag=tag, pubkey=pubkey)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def delete_ssh_pubkey(self, tag: str) -> bool:
        try:
            self.kanidm.delete_person_ssh_pubkeys(self.uuid, tag=tag)
            return True
        except RequestException as e:
            logger.error(e)
            return False


class KanidmGroup(KanidmObject):
    detail_url_name = "claudia:kanidm_group_detail"
    required_attrs = ["spn", "name", "uuid", "classes", "member_of_strs", "direct_member_of_strs", "members_strs"]

    def __init__(self, kanidm: KanidmAPI, attrs: Dict[str, Any] = None):
        self.description, self.gid, self.member_of_strs, self.direct_member_of_strs, self.members_strs = None, None, [], [], []
        super().__init__(kanidm=kanidm, attrs=attrs)

    @cached_property
    def member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.member_of_strs]

    @cached_property
    def direct_member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.direct_member_of_strs]

    @cached_property
    def members(self) -> List['KanidmObject']:
        return [
            self.kanidm.get_object_from_spn(spn)
            for spn in self.members_strs
        ]

    def add_member(self, member: 'KanidmObject') -> bool:
        try:
            self.kanidm.add_member_to_group(self.uuid, member.uuid)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def remove_member(self, member: 'KanidmObject') -> bool:
        try:
            self.kanidm.remove_member_from_group(self.uuid, member.uuid)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def delete(self) -> bool:
        try:
            self.kanidm.delete_group(self.uuid)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_name(self, name: str) -> bool:
        try:
            self.kanidm.set_group_name(self.spn, name=name)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_description(self, description: str) -> bool:
        try:
            self.kanidm.set_group_description(self.spn, description=description)
            return True
        except RequestException as e:
            logger.error(e)
            return False

    def update_posix(self, gid: int) -> bool:
        try:
            self.kanidm.set_group_posix(self.spn, gid=gid)
            return True
        except RequestException as e:
            logger.error(e)
            return False


class KanidmServiceAccount(KanidmObject):
    detail_url_name = "claudia:kanidm_service_account_detail"
    required_attrs = ["spn", "name", "uuid", "classes", "member_of_strs", "direct_member_of_strs"]

    def __init__(self, kanidm: KanidmAPI, attrs: Dict[str, Any] = None):
        self.display_name, self.gid, self.member_of_strs, self.direct_member_of_strs, self.members_strs = None, None, [], [], []
        super().__init__(kanidm=kanidm, attrs=attrs)

    def __str__(self):
        return f"{self.display_name or self.name}"

    @cached_property
    def member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.member_of_strs]

    @cached_property
    def direct_member_of(self) -> List['KanidmGroup']:
        return [self.kanidm.get_group(spn) for spn in self.direct_member_of_strs]

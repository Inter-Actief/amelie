# -*- coding: utf-8 -*-
from typing import List, Dict, Union

from django.conf import settings
from modernrpc.exceptions import AuthenticationFailed

from amelie.api.common import strip_markdown
from amelie.api.decorators import authentication_optional
from amelie.api.exceptions import DoesNotExistError
from amelie.members.models import Committee, CommitteeCategory, Function

from modernrpc.core import rpc_method


@rpc_method(name='getCommitteeStream')
def get_committee_stream() -> Dict[str, List[Dict]]:
    """
    Retrieves a list of all committees per category.

    **Module**: `committee`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `Dict[str, List[Dict]]`: An array of dictionaries per category containing basic committee info.

      The main dictionary keys are the category names, and the lists contain the committees in that category.
      Each returned element in the list has the following fields:

        - id: The identifier for this committee
        - name: The name of this committee
        - imageUrl: An URL of a thumbnail for this committee (optional)

    **Example:**

        --> {"method":"getCommitteeStream", "params":[]}
        <-- {"result": {
                "ICT": [{
                    "id": 12,
                    "name": "AppCie",
                    "imageUrl": "https://url.to/image.png"
                }, {...}, ...],
                "Travel": [...]
        }}
    """
    com_cat = CommitteeCategory.objects.all()

    result = {}

    for category in com_cat:
        committees = Committee.objects.filter(category=category)
        result[category.name] = []
        for committee in committees:
            if committee.abolished is None:
                result[category.name].append({
                    "imageUrl": "%s%s" % (settings.MEDIA_URL, str(committee.logo)) if committee.logo else None,
                    "name": committee.name,
                    "id": committee.id,
                })

    return result


@rpc_method(name='getCommitteeDetailed')
@authentication_optional()
def get_committee_detail(committee_id: int, **kwargs) -> Union[Dict, None]:
    """
    Retrieves details of committee, including its members.

    **Module**: `committee`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - committee_id: The id of the requested item.

    **Return:**
      `Dict`: A dictionary containing detailed committee info.

      The dictionary contains the following fields:

        - id: The identifier for this committee
        - name: The name of this committee
        - imageUrl: An URL of a logo for this committee, or null
        - founded: The date of this committee was founded (RFC3339)
        - description: A description of this committee
        - email: the email address of this committee
        - members: an array of dictionaries representing current members of this committee:
          - name: The full name of this member
          - firstName: The first name of this member
          - lastName: The family name of this member
          - function: The function of this member within the committee
          - phone: The phone number of this member***, otherwise null
          - email: The email address of this member***, otherwise null
            *** Requires an authenticated call and being a member this committee

    **Raises:**

      DoesNotExistError: The committee with this ID does not exist.

      AuthenticationFailed: If the user has no permission to view this committee because it is hidden or abolished.

    **Example:**

        --> {"method":"getCommitteeDetailed", "params":[12]}
        <-- {"result": {
                "name": "AppCie",
                "imageUrl": "https://pbs.twimg.com/profile_image.png",
                "founded": "2011-07-07T18:56:50+00:00",
                "description": "This committee develops and maintains the IApp",
                "email": "nospam@inter-actief.net",
                "members": [{
                    "name":"Donald Duck",
                    "firstName": "Donald",
                    "lastName": "Duck",
                    "function": "Quacker",
                    "phone": null,
                    "email": null
                }, {...}, ...]
        }}
    """
    authentication = kwargs.get('authentication', None)
    result = None

    try:
        result_committee = Committee.objects.get(id=committee_id)
    except Committee.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    person = authentication.represents() if authentication else None

    if ((not result_committee.category) or result_committee.abolished) and (not person or not person.is_board()):
        raise AuthenticationFailed("getCommitteeDetailed")

    functions = Function.objects.filter(committee=result_committee, end=None)
    detailed = person in [l.person for l in functions]

    if result_committee:
        # The dictionary of members
        members = []
        for member in functions:
            members.append({
                "name": member.person.__str__(),
                "firstName": member.person.first_name,
                "lastName": member.person.get_surname(),
                "function": member.function,
                "phone": member.person.telephone if detailed else None,
                "email": member.person.email_address if detailed else None,
            })

        result = {
            "id": result_committee.id,
            "name": result_committee.name,
            "founded": result_committee.founded,
            "description": strip_markdown(result_committee.information).rstrip("\n\r"),
            "members": members,
            "imageUrl": "%s%s" % (settings.MEDIA_URL, str(result_committee.logo)) if result_committee.logo else None,
            "email": result_committee.email,
        }

    return result

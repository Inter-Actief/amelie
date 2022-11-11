# -*- coding: utf-8 -*-
from django.conf import settings
from jsonrpc import jsonrpc_method

from amelie.api.common import strip_markdown
from amelie.api.decorators import authentication_optional
from amelie.api.exceptions import PermissionDeniedError, DoesNotExistError
from amelie.members.models import Committee, CommitteeCategory, Function


@jsonrpc_method('getCommitteeStream() -> Array', validate=True)
def get_committee_stream(request):
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


@jsonrpc_method('getCommitteeDetailed(Number) -> Array', validate=True)
@authentication_optional()
def get_committee_detail(request, nr, authentication=None):
    result = None

    try:
        result_committee = Committee.objects.get(id=nr)
    except Committee.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    person = authentication.represents() if authentication else None

    if ((not result_committee.category) or result_committee.abolished) and (not person or not person.is_board()):
        # TODO Use a JSON-RPC error
        raise PermissionDeniedError()

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

        result = ({
            "name": result_committee.name,
            "founded": result_committee.founded,
            "description": strip_markdown(result_committee.information).rstrip("\n\r"),
            "members": members,
            "imageUrl": "%s%s" % (settings.MEDIA_URL, str(result_committee.logo)) if result_committee.logo else None,
            "email": result_committee.email,
        })

    return result

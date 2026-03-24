from typing import List, Dict

from modernrpc import RpcRequestContext
from modernrpc.exceptions import RPCInvalidParams

from amelie.api.api import api_server
from amelie.api.common import strip_markdown
from amelie.api.decorators import auth_required
from amelie.api.exceptions import DoesNotExistError
from amelie.education.models import Complaint


@api_server.register_procedure(name='getComplaintStream', auth=auth_required('education'), context_target='ctx')
def get_complaint_stream(offset: int, length: int, status: str, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves a list of education complaints.

    **Module**: `education`

    **Authentication:** REQUIRED (Scope: education)

    **Parameters:**
      This method accepts the following parameters:

        - offset: The index offset into the list of complaints to start returning results from.
        - length: The amount of complaints to return (maximum 250, will be limited if higher)
        - status: The status of the complaints to return, one of "all", "open", "closed".

    **Return:**
      `List[Dict]`: An array of dictionaries containing the complaints.

      Each returned element in the list has the following fields:

        - id: The identifier for this complaint.
        - dateTime: The submission date and time of this complaint (RFC3339).
        - type: The type of this complaint.
        - summary: The summary of this complaint.
        - remark: The content of the complaint.
        - supporters: The amount of supporters for this complaint (includes the original reporter).
        - hasSupported: true if the authenticated person has supported this complaint, otherwise false.
        - course: The course concerning this complaint, can be null.
        - subject: The subject concerning the course of this complaint, can be null.
        - year: The first year of the academic year in which the course was given, can be null.
        - period: The period of the academic year in which the course was given, can be null.
        - isCompleted: Boolean indicating if the complaint was marked as completed and is closed.

    **Raises:**

      InvalidParamsError: The value of the status parameter was invalid.

    **Example:**

        --> {"method": "getComplaintStream", "params": [0, 2]}
        <-- {"result": [{
                "id": 28,
                "dateTime": "2014-07-02T018:00:00+02:00",
                "type": "Other",
                "summary": "So many bugs, so many...,
                "remark": "Description of the complaint",
                "supporters": 42,
                "hasSupported": false,
                "course": "Computer Systems",
                "subject": "Programming",
                "year": 2016,
                "period": "K2",
                "isCompleted": false
              }, {...}]
        }
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    if status not in ['all', 'open', 'closed']:
        raise RPCInvalidParams("The provided status of complaints can only be 'all', 'open' or 'closed'")

    # All complaints
    complaints = Complaint.objects.filter(public=True)

    # Open complaints
    if status == 'open':
        complaints = complaints.filter(completed=False)

    # Closed complaints
    elif status == 'closed':
        complaints = complaints.filter(completed=True)

    # Limit amount to 250
    if length > 250:
        length = 250

    result = []
    for complaint in complaints[offset:length + offset]:

        if person == complaint.reporter or person in complaint.people.all():
            has_supported = True
        else:
            has_supported = False

        result.append({
            "id": complaint.id,
            "dateTime": complaint.published.isoformat(),
            "type": complaint.subject,
            "summary": complaint.summary,
            "remark": strip_markdown(complaint.comment),
            "supporters": complaint.people.count() + 1,
            "hasSupported": has_supported,
            "course": complaint.course.name if complaint.course else None,
            "subject": complaint.part,
            "year": complaint.year,
            "period": complaint.period,
            "isCompleted": complaint.completed
        })
    return result


@api_server.register_procedure(name='addComplaintSupport', auth=auth_required('education'), context_target='ctx')
def add_complaint_support(complaint_id: int, ctx: RpcRequestContext = None, **kwargs) -> bool:
    """
    Adds support of the authenticated person to a specific complaint.

    **Module**: `education`

    **Authentication:** REQUIRED (Scope: education)

    **Parameters:**
      This method accepts the following parameters:

        - id: The identifier of any existing complaint.

    **Return:**
      `bool`: `true` if successful, otherwise `false`

    **Raises:**

      DoesNotExistError: The complaint with the given identifier does not exist.

    **Example:**

        --> {"method": "addComplaintSupport", "params": [27]}
        <-- {"result": true}
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    try:
        complaint = Complaint.objects.get(id=complaint_id)
    except Complaint.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if person not in complaint.people.all() and person != complaint.reporter:
        complaint.people.add(person)
        complaint.save()
        return True
    else:
        return False


@api_server.register_procedure(name='removeComplaintSupport', auth=auth_required('education'), context_target='ctx')
def remove_complaint_support(complaint_id: int, ctx: RpcRequestContext = None, **kwargs) -> bool:
    """
    Removes support of the authenticated person of a specific complaint.

    **Module**: `education`

    **Authentication:** REQUIRED (Scope: education)

    **Parameters:**
      This method accepts the following parameters:

        - id: The identifier of any existing complaint.

    **Return:**
      `bool`: `true` if successful, otherwise `false`

    **Raises:**

      DoesNotExistError: The complaint with the given identifier does not exist.

    **Example:**

        --> {"method": "removeComplaintSupport", "params": [27]}
        <-- {"result": true}
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    try:
        complaint = Complaint.objects.get(id=complaint_id)
    except Complaint.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if person in complaint.people.all() and person != complaint.reporter:
        complaint.people.remove(person)
        complaint.save()
        return True
    else:
        return False

from django.utils import timezone
from jsonrpc import jsonrpc_method
from jsonrpc.exceptions import InvalidParamsError

from amelie.api.common import parse_datetime, strip_markdown
from amelie.api.decorators import authentication_required
from amelie.api.exceptions import DoesNotExistError
from amelie.education.models import Complaint, Course
from amelie.education.views import send_new_complaint_notification


@jsonrpc_method('getComplaintStream(Number, Number, String) -> Array', validate=True)
@authentication_required("education")
def get_complaint_stream(request, offset, length, status, authentication=None):
    person = authentication.represents()

    if status not in ['all', 'open', 'closed']:
        raise InvalidParamsError("The provided status of complaints can only be 'all', 'open' or 'closed'")

    # All complaints
    complaints = Complaint.objects.filter(public=True)

    # Open complaints
    if status == 'open':
        complaints = complaints.filter(completed=False)

    # Closed complaints
    elif status == 'closed':
        complaints = complaints.filter(completed=True)

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


@jsonrpc_method('addComplaintSupport(Number) -> Boolean', validate=True)
@authentication_required("education")
def add_complaint_support(request, complaint_id, authentication=None):
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


@jsonrpc_method('removeComplaintSupport(Number) -> Boolean', validate=True)
@authentication_required("education")
def remove_complaint_support(request, complaint_id, authentication=None):
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

from django.urls import reverse
from django.conf import settings
from jsonrpc import jsonrpc_method
from jsonrpc.exceptions import InvalidParamsError

from amelie.api.decorators import authentication_required


@jsonrpc_method('getUserId() -> Object', validate=True)
@authentication_required()
def get_person_id(request, authentication=None):
    person = authentication.represents()

    return {
        "userId": person.id,
    }


@jsonrpc_method('getPersonDetails() -> Object', validate=True)
@authentication_required("account")
def get_person_details(request, authentication=None):
    person = authentication.represents()

    if person is not None:
        student_id = None
        employee_id = None

        if hasattr(person, 'student'):
            student_id = person.student.student_number()

        if hasattr(person, 'employee'):
            employee_id = 'm{:0>7}'.format(person.employee.number)

        image_url = None
        if person.picture:
            image_url = request.build_absolute_uri(reverse('members:person_picture',
                                                           kwargs={"id": person.id, "slug": person.slug}))

        result = {
            "userId": person.id,
            "name": person.incomplete_name(),
            "firstName": person.first_name,
            "lastName": person.get_surname(),
            "birthdate": person.date_of_birth,
            "board": person.is_board(),
            "candidateBoard": person.is_candidate_board(),
            "member": person.is_member(),
            "hasCommittees": person.is_active_member(),
            "hasActivityDirectDebit": len(person.has_mandate_activities()) > 0,
            "username": person.account_name,
            "studentId": student_id,
            "employeeId": employee_id,
            "email": person.email_address,
            "imageUrl": image_url,
            "languagePreference": person.preferred_language,
        }
        return result
    else:
        return None


@jsonrpc_method('getPersonCommittees() -> Object', validate=True)
@authentication_required("account")
def get_person_committees(request, authentication=None):
    person = authentication.represents()

    if person is not None:
        positions = person.function_set.all()
        result = []
        for position in positions:
            result.append({
                "position": position.function,
                "begin": position.begin.isoformat(),
                "end": position.end.isoformat() if position.end else None,
                "committee": {
                    "id": position.committee.id,
                    "name": position.committee.name,
                    "abolished": position.committee.abolished.isoformat() if position.committee.abolished else None,
                },
            })
        return result
    else:
        return None


@jsonrpc_method('getPersonMembership() -> Object', validate=True)
@authentication_required("account")
def get_person_membership(request, authentication=None):
    person = authentication.represents()

    if person.membership is not None:
        result = {
            "type": person.membership.type.name,
            "year": person.membership.year,
            "payment": None,
            "hasEnded": person.membership.ended if person.membership.ended else False,
        }

        if hasattr(person.membership, "payment") and person.membership.payment is not None:
            result["payment"] = {
                "date": person.membership.payment.date,
                "method": {
                    "name": person.membership.payment.payment_type.name,
                    "description": person.membership.payment.payment_type.description,
                },
                "amount": person.membership.payment.amount,
            }

        return result
    else:
        return None


@jsonrpc_method('setLanguagePreference(String) -> Boolean', validate=True)
@authentication_required("account")
def set_language_preference(request, language, authentication=None):
    person = authentication.represents()

    if any(language in code for code, lang in settings.LANGUAGES):
        person.preferred_language = language
        person.save()
        return True
    else:
        raise InvalidParamsError("Invalid language code parameter.")

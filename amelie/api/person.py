from typing import Dict, List, Union

from django.urls import reverse
from django.conf import settings

from amelie.api.decorators import authentication_required

from modernrpc.core import rpc_method, REQUEST_KEY
from modernrpc.exceptions import RPCInvalidParams


@rpc_method(name='getUserId')
@authentication_required()
def get_person_id(**kwargs) -> Dict:
    """
    Retrieves the user ID of the currently authenticated person.

    **Module**: `person`

    **Authentication:** REQUIRED (Scope: _any_)

    **Parameters:** _(none)_

    **Return:**
      `Dict`: A dictionary containing the following field:

        - userId: The user ID of this person

    **Raises:**
      NotLoggedInError: Token was not recognized or already revoked.

    **Example:**

        --> {"method":"getUserId", "params":[]}
        <-- {"result": {"userId": 1234}}
    """
    person = kwargs.get('authentication').represents()

    return {
        "userId": person.id,
    }


@rpc_method(name='getPersonDetails')
@authentication_required("account")
def get_person_details(**kwargs) -> Union[Dict, None]:
    """
    Retrieves details of the currently authenticated person.

    **Module**: `person`

    **Authentication:** REQUIRED (Scope: account)

    **Parameters:** _(none)_

    **Return:**
      `Dict`: A dictionary containing the following fields:

        - name: The full name of this person
        - firstName: The first name of this person
        - lastName: The last name of this person
        - birthdate: The birthdate of this person
        - board: true if this person is a board member, false otherwise
        - candidateBoard: true if this person is a candidate board member, false otherwise
        - member: true if this person is a member, false otherwise
        - hasCommittees: true if this member has joined any committees, false otherwise
        - hasActivityDirectDebit: true if this person has signed a debit contract, false otherwise
        - username: The username of this person, can be empty or null
        - studentId: The student ID of this person, can be null
        - employeeId: The employee ID of this person, can be null
        - email: The email address of this person
        - languagePreference: The preferred language for this user, either "nl" or "en"
        - imageUrl: The profile image URL for the authenticated user

    **Raises:**
      NotLoggedInError: Token was not recognized or already revoked.

    **Example:**

        --> {"method":"getPersonDetails", "params":[]}
        <-- {"result": {
               "name": "Donald D. Duck",
               "firstName": "Donald",
               "lastName": "Duck",
               "birthdate": "1954-02-19",
               "board": false
               "candidateBoard": false,
               "member": true,
               "hasCommittees": true,
               "hasActivityDirectDebit": true,
               "username": "duckdd",
               "studentId": "s1234567",
               "employeeId": null,
               "email": "d.d.duck@student.utwente.nl",
               "languagePreference": "nl",
               "imageUrl": "https://media.ia.utwente.nl/amelie/pasfoto/a3d248c5-e840-4de1-88aa-a2d2958ef66f.jpg"
        }}
    """
    request = kwargs.get(REQUEST_KEY)
    person = kwargs.get('authentication').represents()

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

        return {
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
    else:
        return None


@rpc_method(name='getPersonCommittees')
@authentication_required("account")
def get_person_committees(**kwargs) -> Union[List[Dict], None]:
    """
    Retrieves a list of committees in which the currently authenticated person has been a
    member of, or is currently active in.

    **Module**: `person`

    **Authentication:** REQUIRED (Scope: account)

    **Parameters:** _(none)_

    **Return:**
      `Union[List[Dict], None]`: An array of dictionaries containing the committee information,
                                 or null if the current user has no associated person.

      Each returned element in the list has the following fields:

        - position: The position of this person in this committee
        - end: The date on which this person was last member of this committee, otherwise null
        - begin: The date on which this person first joined this committee
        - committee: The name of this committee

    **Raises:**
      NotLoggedInError: Token was not recognized or already revoked.

    **Example:**

        --> {"method":"getPersonCommittees", "params":[]}
        <-- {"result": [{
               "position": "Lead Developer Duckstad",
               "end": null,
               "begin": "1954-02-19",
               "committee": "F.C. Duckstad"
        }]}
    """
    person = kwargs.get('authentication').represents()

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


@rpc_method(name='getPersonMembership')
@authentication_required("account")
def get_person_membership(**kwargs) -> Union[Dict, None]:
    """
    Retrieves the active membership details of the currently authenticated person.

    **Module**: `person`

    **Authentication:** REQUIRED (Scope: account)

    **Parameters:** _(none)_

    **Return:**
      `Union[Dict, None]`: A dictionary with the following fields, or null if the person has no active membership:

        - type: The type of membership
        - year: The year of the active membership
        - hasEnded: Value indicating whether the membership has ended, either true or false
        - payment: Details regarding the payment of this membership
          - amount: The cost of the active membership
          - date: Date on which the payment was processed
          - method: Details regarding the payment method of the active membership
            - name: Name of the payment method
            - description: Description of the payment method

    **Raises:**
      NotLoggedInError: Token was not recognized or already revoked.

    **Example:**

        --> {"method":"getPersonMembership", "params":[]}
        <-- {"result": {
               "type": "Primair jaarlid",
               "year": 2022,
               "hasEnded": false
               "payment": {
                 "amount": "8.50",
                 "date": "2022-07-01",
                 "method": {
                   "name": "Annual authorization",
                   "description": "Machtiging via Automatische Incasso."
                 }
               }
        }}
    """
    person = kwargs.get('authentication').represents()

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


@rpc_method(name='setLanguagePreference')
@authentication_required("account")
def set_language_preference(language: str, **kwargs) -> bool:
    """
    Sets the language preference for the currently authenticated person across all Inter-Actief services.

    **Module**: `person`

    **Authentication:** REQUIRED (Scope: account)

    **Parameters:**
      This method accepts the following parameters:

        - language: The preferred language (either 'nl' or 'en')

    **Return:**
      `bool`: If setting the preference was successful or not.

    **Raises:**

      InvalidParamsError: The `language` parameter was not valid.

      NotLoggedInError: Token was not recognized or already revoked.

    **Example:**

        --> {"method":"setLanguagePreference", "params":["en"]}
        <-- {"result": true}
    """
    person = kwargs.get('authentication').represents()

    if any(language in code for code, lang in settings.LANGUAGES):
        person.preferred_language = language
        person.save()
        return True
    else:
        raise RPCInvalidParams("Invalid language code parameter.")

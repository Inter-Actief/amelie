from typing import List, Dict, Union

from modernrpc import RpcRequestContext
from modernrpc.exceptions import RPCInvalidParams

from django.conf import settings

from amelie.api.api import api_server
from amelie.api.common import parse_datetime
from amelie.api.decorators import auth_required
from amelie.personal_tab.models import DebtCollectionInstruction
from amelie.personal_tab.models import Transaction


@api_server.register_procedure(name='getRfidCards', auth=auth_required('transaction'), context_target='ctx')
def get_rfid_cards(ctx: RpcRequestContext = None, **kwargs) -> Union[List[Dict], None]:
    """
    Retrieves a list of RFID-cards registered to the authenticated person.

    **Module**: `personal_tab`

    **Authentication:** REQUIRED (Scope: transaction)

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the RFID-cards.

      Each returned element in the list has the following fields:

        - isActivated: Boolean value indicating the activation status of this card.
        - code: The RFID unique ID associated with this card.
        - type: The type of this card.

    **Example:**

        --> {"method": "getRfidCards", "params": []}
        <-- {"result": [{
                "isActivated": true,
                "code": "00,0a:00:00:00",
                "type": "Mifare 1K (Collegekaart/Gebouwpas)"
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    if person is not None:
        rfids = person.rfidcard_set.all()
        result = []
        for rfid in rfids:
            result.append({
                "code": rfid.code,
                "type": str(rfid.type()),
                "isActivated": rfid.active,
            })
        return result
    else:
        return None


@api_server.register_procedure(name='getTransactions', auth=auth_required('transaction'), context_target='ctx')
def get_transactions(begin_date_str: str, end_date_str: str, ctx: RpcRequestContext = None, **kwargs) -> Union[List[Dict], None]:
    """
    Retrieves a list of transactions associated with the authenticated person.

    **Module**: `personal_tab`

    **Authentication:** REQUIRED (Scope: transaction)

    **Parameters:**
      This method accepts the following parameters:

        - begin_date_str: The minimal begin date, RFC3339 (inclusive)
        - end_date_str: The maximal end date, RFC3339 (exclusive)

    **Return:**
      `List[Dict]`: An array of dictionaries containing the transactions.

      Each returned element in the list has the following fields:

        - person: The name of the person who performed the transaction.
        - description: The description of the transaction.
        - date: The date of the transaction (RFC3339).
        - amount: The amount of money reduced by the transaction, can be negative.

    **Raises:**

      InvalidParamsError: The value of (one of) the date parameter(s) was invalid.

    **Example:**

        --> {"method": "getTransactions", "params": ["2014-07-01T00:00:00+02:00", "2014-07-31T23:59:59+02:00"]}
        <-- {"result": [{
                "person": "D. D. Duck",
                "description": "A very bright description",
                "date": "2014-07-02T018:00:00+02:00",
                "amount": "5.00"
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    if person is not None:
        # Sanitize date strings
        try:
            begin_date = parse_datetime(begin_date_str)
            end_date = parse_datetime(end_date_str)
        except ValueError as e:
            raise RPCInvalidParams("Dates should be formatted as ISO 8601 (yyyy-mm-ddThh:mm:ss+hhmm)")

        transactions = Transaction.objects.filter(person=person,
                                                  date__range=(begin_date, end_date)).order_by('-added_on')
        result = []

        for transaction in transactions:
            result.append({
                "date": transaction.date.isoformat(),
                "amount": transaction.price,
                "person": transaction.person.incomplete_name(),
                "description": transaction.description,
            })

        return result
    else:
        return None


@api_server.register_procedure(name='getDirectDebits', auth=auth_required('transaction'), context_target='ctx')
def get_direct_debits(ctx: RpcRequestContext = None, **kwargs):
    """
    Retrieves a list of direct debits associated with the authenticated person.

    **Module**: `personal_tab`

    **Authentication:** REQUIRED (Scope: transaction)

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the direct debits.

      Each returned element in the list has the following fields:

        - date: The date of the direct debit (RFC3339).
        - description: A description of the direct debit.
        - amount: The amount of money requested by the direct debit.

    **Example:**

        --> {"method": "getDirectDebits", "params": []}
        <-- {"result": [{
                "date": "2017-02-14",
                "description": "A very informative description",
                "amount": "12.00"
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    if person is not None:
        direct_debits = DebtCollectionInstruction.objects.filter(authorization__person=person)
        result = []

        for direct_debit in direct_debits:
            result.append({
                "date": direct_debit.batch.execution_date.isoformat(),
                "description": direct_debit.description,
                "amount": direct_debit.amount,
            })

        return result
    else:
        return None


@api_server.register_procedure(name='getMandates', auth=auth_required('transaction'), context_target='ctx')
def get_mandates(ctx: RpcRequestContext = None, **kwargs):
    """
    Retrieves a list of mandates associated with the authenticated person.

    **Module**: `personal_tab`

    **Authentication:** REQUIRED (Scope: transaction)

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the mandates.

      Each returned element in the list has the following fields:

        - reference: The reference id of the mandate.
        - type: The type of mandate.
        - iban: The IBAN associated with the mandate.
        - accountHolder: The name of the person holding the account.
        - beginDate: The start date of the mandate, either RFC3339 format or "old".
        - endDate: The end date of the mandate, can be null.

    **Example:**

        --> {"method": "getMandates", "params": []}
        <-- {"result": [{
                "accountHolder": "D. D. Duck",
                "endDate": null,
                "reference": "IA-MNDT-00000000",
                "type": "Consumptions, activities and miscellaneous",
                "iban": "XX00XXXX0000000000",
                "beginDate": "2017-01-26"
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    person = authentication.represents()

    if person is not None:
        mandates = person.authorization_set.all()
        date_old_mandates = settings.DATE_PRE_SEPA_AUTHORIZATIONS
        result = []

        for mandate in mandates:
            if mandate.start_date == date_old_mandates:
                begin_date = "old"
            else:
                begin_date = mandate.start_date.isoformat()

            result.append({
                "reference": mandate.authorization_reference(),
                "type": mandate.authorization_type.name,
                "iban": mandate.iban,
                "accountHolder": mandate.account_holder_name,
                "beginDate": begin_date,
                "endDate": mandate.end_date.isoformat() if mandate.end_date else None,
            })

        return result
    else:
        return None

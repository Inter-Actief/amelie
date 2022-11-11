from django.conf import settings
from jsonrpc import jsonrpc_method
from jsonrpc.exceptions import InvalidParamsError

from amelie.api.common import parse_datetime
from amelie.api.decorators import authentication_required
from amelie.personal_tab.models import DebtCollectionInstruction
from amelie.personal_tab.models import Transaction


@jsonrpc_method('getRfidCards() -> Object', validate=True)
@authentication_required("transaction")
def get_rfid_cards(request, authentication=None):
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


@jsonrpc_method('getTransactions(String, String) -> Array', validate=True)
@authentication_required("transaction")
def get_transactions(request, beginDateString, endDateString, authentication=None):
    person = authentication.represents()

    if person is not None:
        # Sanitize date strings
        try:
            beginDate = parse_datetime(beginDateString)
            endDate = parse_datetime(endDateString)
        except ValueError as e:
            raise InvalidParamsError("Dates should be formatted as ISO 8601 (yyyy-mm-ddThh:mm:ss+hhmm)")

        transactions = Transaction.objects.filter(person=person, date__range=(beginDate, endDate)).order_by('-added_on')
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


@jsonrpc_method('getDirectDebits() -> Object', validate=True)
@authentication_required("transaction")
def get_direct_debits(request, authentication=None):
    person = authentication.represents()

    if person is not None:
        directDebits = DebtCollectionInstruction.objects.filter(authorization__person=person)
        result = []

        for directDebit in directDebits:
            result.append({
                "date": directDebit.batch.execution_date.isoformat(),
                "description": directDebit.description,
                "amount": directDebit.amount,
            })

        return result
    else:
        return None


@jsonrpc_method('getMandates() -> Object', validate=True)
@authentication_required("transaction")
def get_mandates(request, authentication=None):
    person = authentication.represents()

    if person is not None:
        mandates = person.authorization_set.all()
        date_old_mandates = settings.DATE_PRE_SEPA_AUTHORIZATIONS
        result = []

        for mandate in mandates:
            beginDate = None
            if mandate.start_date == date_old_mandates:
                beginDate = "old"
            else:
                beginDate = mandate.start_date.isoformat()

            result.append({
                "reference": mandate.authorization_reference(),
                "type": mandate.authorization_type.name,
                "iban": mandate.iban,
                "accountHolder": mandate.account_holder_name,
                "beginDate": beginDate,
                "endDate": mandate.end_date.isoformat() if mandate.end_date else None,
            })

        return result
    else:
        return None


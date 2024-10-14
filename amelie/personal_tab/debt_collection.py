import datetime

from django.db.models import Sum, Q
from django.template.defaultfilters import date as _date
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from amelie.members.models import Person, Membership, PaymentType, Payment
from amelie.personal_tab.models import Transaction, DebtCollectionInstruction, DebtCollectionBatch, \
    DebtCollectionTransaction, ContributionTransaction, ReversalTransaction, Reversal, Amendment
from amelie.tools.encodings import normalize_to_ascii


def authorization_contribution(person):
    """
    Returns the most appropriate contribution authorization for a given person.

    Returns the first found authorization in the following order:
    - Active authorization contribution
    - Active authorization contribution (old version)

    Returns None if no corresponding authorization is found.

    :type person: Person
    """
    # 2   Contribution
    # 4   Contribution (old version)
    authorizations = person.authorization_set.filter(is_signed=True, end_date__isnull=True,
                                                     authorization_type__contribution=True).order_by('authorization_type__id')
    return authorizations[0] if authorizations else None


def authorization_cookie_corner(person):
    """
    Returns the most appropriate cookie corner authorization for a given person.

    Returns the first found authorization in the following order:
    - Active authorization Consumptions, activities and other
    - Active authorization Consumptions and activities
    - Active authorization Consumptions
    - Terminated authorization Consumptions, activities and other
    - Terminated authorization Consumptions and activities
    - Terminated authorization Consumptions

    Returns None if no corresponding authorization is found.

    :type person: Person
    """
    # 1   Consumptions, activities and other
    # 4   Consumptions and activities
    # 5   Consumptions

    authorizations = person.authorization_set.filter(
                        is_signed=True, end_date__isnull=True, authorization_type__consumptions=True
                     ).order_by('authorization_type__id')

    authorization = authorizations[0] if authorizations else None

    if not authorizations:
        authorizations_old = person.authorization_set.filter(
                                is_signed=True, authorization_type__consumptions=True
                             ).order_by('authorization_type__id')

        authorization = authorizations_old[0] if authorizations_old else None

    return authorization


def generate_contribution_instructions(year):
    """
    Generate DebtCollectionInstruction objects to collect the contribution of a given association year.

    The DebtCollectionInstruction objects that are returned are not saved yet.
    """
    memberships = Membership.objects.filter(Q(ended__gt=datetime.date.today()) | Q(ended__isnull=True),
                                            payment__isnull=True, type__price__gt=0, year=year)

    result = {
        'ongoing_frst': [],
        'frst': [],
        'rcur': []
    }

    for m in memberships:
        person = m.member
        price = m.type.price
        sumf = ("%.2f" % price).replace('.', ',')

        authorization = authorization_contribution(person)

        if not authorization:
            # Ignore people without authorization
            continue

        name = person.incomplete_name()

        with translation.override(person.preferred_language):
            description = _('Contribution Inter-Actief {membership_type} {name} Questions? call 053-489 3756')\
                .format(membership_type=m.type.name, name=name)
            description = normalize_to_ascii(description)

        instruction = None

        sequence_type = authorization.next_sequence_type()
        if sequence_type:
            instruction = DebtCollectionInstruction(amount=price, authorization=authorization, description=description,
                                                    amendment=authorization.next_amendment())

        row = {
            'person': person,
            'authorization': authorization,
            'membership': m,
            'sum': price,
            'sumf': sumf,
            'instruction': instruction
        }

        if not sequence_type:
            result['ongoing_frst'].append(row)
        elif sequence_type == DebtCollectionBatch.SequenceTypes.FRST:
            result['frst'].append(row)
        else:
            result['rcur'].append(row)

    return result


def filter_contribution_instructions(rows, post):
    res = []

    for row in rows:
        if 'contribution_%i' % row['membership'].id in post:
            res.append(row)

    return res


def save_contribution_instructions(rows, batch):
    """
    :type rows: list
    :type batch: DebtCollectionBatch
    """
    execution_date = batch.execution_date

    debt_collection_datetime = timezone.make_aware(datetime.datetime.combine(execution_date, datetime.time(0, 0)),
                                                   timezone.get_default_timezone())
    # Annual authorization
    payment_method = PaymentType.objects.get(id=4)

    for row in rows:
        person = row['person']
        price = row['sum']
        membership = row['membership']
        instruction = row['instruction']

        with translation.override(person.preferred_language):
            dct_description = _('Direct withdrawal of contribution {date}').format(date=_date(execution_date, "j F Y"))
            ct_description = _('Contribution {membership_type} ({begin_year}/{end_year})').format(
                membership_type=membership.type.name, begin_year=membership.year, end_year=(membership.year + 1)
            )

        instruction.batch = batch
        instruction.save()

        instruction.end_to_end_id = instruction.debt_collection_reference()
        instruction.save()

        ct = ContributionTransaction(date=debt_collection_datetime, price=price, person=person,
                                     description=ct_description, membership=membership, debt_collection=instruction)
        ct.save()

        dct = DebtCollectionTransaction(date=debt_collection_datetime, price=-price, person=person,
                                        description=dct_description, debt_collection=instruction)
        dct.save()

        payment = Payment(date=execution_date, payment_type=payment_method, amount=price, membership=membership)
        payment.save()


def generate_cookie_corner_instructions(end_date):
    all_transactions = Transaction.objects.filter(debt_collection=None)

    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    begin_date = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=timezone.utc)

    all_transactions = all_transactions.filter(date__gte=begin_date, date__lt=end_date)

    # Order only by person, so distinct works as intended. See Django manual.
    people = all_transactions.filter(person__isnull=False).order_by('person').distinct().values('person')
    results = {
        'negative': [],
        'no_authorization': [],
        'terminated_authorization_frst': [],
        'terminated_authorization_rcur': [],
        'ongoing_frst': [],
        'frst': [],
        'rcur': []
    }

    end_date_timezone_amsterdam = end_date.astimezone(timezone.get_default_timezone())

    for p in people:
        person = Person.objects.get(id=p['person'])
        transactions = all_transactions.filter(person=person)
        price = transactions.aggregate(Sum('price'))['price__sum']
        sumf = ("%.2f" % price).replace('.', ',')

        if price == 0:
            continue

        authorization = authorization_cookie_corner(person)
        instruction = None
        sequence_type = None

        if authorization and price > 0:
            sequence_type = authorization.next_sequence_type()

            name = person.incomplete_name()

            with translation.override(person.preferred_language):
                description = _('Personal tab Inter-Actief till {date} {name} Questions? call 053-489 3756').format(
                    date=_date(end_date_timezone_amsterdam, "j F Y H:i"), name=name
                )
                description = normalize_to_ascii(description)

            if sequence_type:
                instruction = DebtCollectionInstruction(amount=price, authorization=authorization,
                                                        description=description,
                                                        amendment=authorization.next_amendment())

        row = {
            'person': person,
            'authorization': authorization,
            'sum': price,
            'sumf': sumf,
            'instruction': instruction,
            'transactions': transactions
        }

        if price < 0:
            results['negative'].append(row)
        elif not authorization:
            results['no_authorization'].append(row)
        elif not sequence_type:
            results['ongoing_frst'].append(row)
        elif not authorization.is_active():
            if sequence_type == DebtCollectionBatch.SequenceTypes.FRST:
                results['terminated_authorization_frst'].append(row)
            else:
                results['terminated_authorization_rcur'].append(row)
        elif sequence_type == DebtCollectionBatch.SequenceTypes.FRST:
            results['frst'].append(row)
        else:
            results['rcur'].append(row)

    return results


def filter_cookie_corner_instructions(rows, post):
    res = []

    for row in rows:
        if 'cookie_corner_%i' % row['person'].id in post:
            res.append(row)

    return res


def save_cookie_corner_instructions(rows, batch):
    """
    :type rows: list
    :type batch: DebtCollectionBatch
    """
    timezone_amsterdam = timezone.get_default_timezone()
    execution_date = batch.execution_date

    debt_collection_datetime = datetime.datetime.combine(execution_date, datetime.time(0, 0)).replace(tzinfo=timezone_amsterdam)

    for row in rows:
        person = row['person']
        price = row['sum']
        instruction = row['instruction']
        transactions = row['transactions']

        with translation.override(person.preferred_language):
            description = _('Direct withdrawal personal tab {date}').format(date=_date(execution_date, "j F Y"))

        instruction.batch = batch
        instruction.save()

        instruction.end_to_end_id = instruction.debt_collection_reference()
        instruction.save()

        for transaction in transactions:
            transaction.debt_collection = instruction
            transaction.save()

        dct = DebtCollectionTransaction(date=debt_collection_datetime, price=-price, person=person,
                                        description=description, debt_collection=instruction)
        dct.save()


def process_reversal(reversal, actor):
    """
    :type reversal: Reversal
    :type actor: Person
    """
    timezone_amsterdam = timezone.get_default_timezone()
    instruction = reversal.instruction
    person = instruction.authorization.person

    reversal_datetime = datetime.datetime.combine(reversal.date, datetime.time(0, 0)).replace(tzinfo=timezone_amsterdam)
    with translation.override(person.preferred_language):
        description = _('Reversal of direct withdrawal {date}').format(date=_date(instruction.batch.execution_date, "j F Y"))

    rt = ReversalTransaction(reversal=reversal, date=reversal_datetime, price=instruction.amount,
                             person=person, description=description, added_by=actor)
    rt.save()

    for ct in ContributionTransaction.objects.filter(debt_collection=instruction):
        # Only reverse real transactions, do not reverse other reversals.
        if ct.price > 0:
            Payment.objects.filter(membership__contributiontransaction=ct).delete()

            with translation.override(ct.person.preferred_language):
                description = _('Reversal contribution {membership_type} ({start_year}/{end_year})').format(
                    membership_type=ct.membership.type.name, start_year=ct.membership.year,
                    end_year=ct.membership.year + 1
                )
            cct = ContributionTransaction(date=reversal_datetime, price=-ct.price, person=ct.person,
                                          description=description, membership=ct.membership)
            cct.save()


def process_amendment(authorization, date, iban, bic, reason):
    """
    Process an amendment to an authorization.

    Make sure you call this method only from within a database transaction!
    """
    other_bank = bic != authorization.bic
    amendment = Amendment(authorization=authorization, date=date, previous_iban=authorization.iban,
                          previous_bic=authorization.bic, other_bank=other_bank, reason=reason)
    amendment.save()
    authorization.iban = iban
    authorization.bic = bic
    authorization.save()

    return amendment

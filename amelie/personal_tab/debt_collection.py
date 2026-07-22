import datetime
from datetime import timezone as tz

from django.db import transaction
from django.db.models import Sum, Q
from django.template.defaultfilters import date as _date
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from amelie.members.models import Person, Membership
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


def generate_contribution_instructions(years):
    """
    Generate DebtCollectionInstruction objects to collect the contribution of a given association year.

    The DebtCollectionInstruction objects that are returned are not saved yet.
    """
    result = {
        'ongoing_frst': [],
        'frst': [],
        'rcur': []
    }

    unpaid_membership_transactions = ContributionTransaction.objects.filter(
        settlement=None, membership__type__price__gt=0, year__in=years
    )
    for umt in unpaid_membership_transactions:
        person = umt.membership.member
        sumf = ("%.2f" % umt.price).replace('.', ',')

        authorization = authorization_contribution(person)

        if not authorization:
            # Ignore people without authorization
            continue

        name = person.incomplete_name()

        with translation.override(person.preferred_language):
            description = _('Contribution Inter-Actief {membership_year} {membership_type} {name} Questions? Email treasurer@inter-actief.net')\
                .format(membership_year="{}-{}".format(umt.membership.year, umt.membership.year + 1), membership_type=umt.membership.type.name, name=name)
            description = normalize_to_ascii(description)

        instruction = None

        sequence_type = authorization.next_sequence_type()
        if sequence_type:
            instruction = DebtCollectionInstruction(
                amount=umt.price, authorization=authorization, description=description,
                mendment=authorization.next_amendment()
            )

        row = {
            'person': person,
            'authorization': authorization,
            'transaction': umt,
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
    for row in rows:
        person: Person = row['person']
        contribution_transaction: ContributionTransaction = row['transaction']
        instruction: DebtCollectionInstruction = row['instruction']

        with translation.override(person.preferred_language):
            dct_description = _('Direct withdrawal of contribution {date}').format(
                date=_date(execution_date, "j F Y")
            )

        instruction.batch = batch
        instruction.save()

        instruction.end_to_end_id = instruction.debt_collection_reference()
        instruction.save()

        # Set the contribution transaction settlement, so it is considered paid.
        contribution_transaction.settlement = instruction
        contribution_transaction.save()

        dct = DebtCollectionTransaction(
            date=debt_collection_datetime, price=-instruction.amount, person=person,
            description=dct_description, settlement=instruction
        )
        dct.save()


def generate_cookie_corner_instructions(end_date):
    all_transactions = Transaction.objects.filter(settlement=None, date__lt=end_date)

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
                description = _('Personal tab Inter-Actief till {date} {name} Questions? Email treasurer@inter-actief.net').format(
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
            transaction.settlement = instruction
            transaction.save()

        dct = DebtCollectionTransaction(date=debt_collection_datetime, price=-price, person=person,
                                        description=description, settlement=instruction)
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

    # Filter for real (positive) ContributionTransactions to avoid reversing other reversals.
    for ct in ContributionTransaction.objects.filter(settlement=instruction, price__gt=0):
        with translation.override(ct.person.preferred_language):
            description = _('Reversal contribution {membership_type} ({start_year}/{end_year})').format(
                membership_type=ct.membership.type.name, start_year=ct.membership.year,
                end_year=ct.membership.year + 1
            )

        # TODO: This next bit is a bit convoluted, but it is the quickest way to get it working nicely.
        #       Maybe another refactor step is necessary to get rid of all of these extra ContributionTransactions.
        #       albertskja - 2026-07-22

        # Create a ContributionTransaction to reverse the original transaction which was marked paid in the debt collection instruction
        cct = ContributionTransaction(date=reversal_datetime, price=-ct.price, person=ct.person,
                                      description=description, membership=ct.membership)
        cct.save()
        # And create another ContributionTransaction to mark that the contribution still needs to be paid.
        cct = ContributionTransaction(date=reversal_datetime, price=ct.price, person=ct.person,
                                      description=ct.description, membership=ct.membership)
        cct.save()


def edit_reversal(reversal, actor):
    """
    :type reversal: Reversal
    :type actor: Person
    """
    timezone_amsterdam = timezone.get_default_timezone()
    reversal_datetime = datetime.datetime.combine(reversal.date, datetime.time(0, 0)).replace(tzinfo=timezone_amsterdam)

    rt = ReversalTransaction.objects.get(reversal=reversal)
    rt.date = reversal_datetime
    rt.added_by = actor
    rt.save()


@transaction.atomic
def delete_reversal(reversal):
    """
    :type reversal: Reversal
    """
    rt = ReversalTransaction.objects.get(reversal=reversal)

    # TODO: This next bit is a bit convoluted, but we need to clean up what we did in `process_reversal`.
    #       Maybe another refactor step is necessary to get rid of all of this hassle with ContributionTransactions.
    #       albertskja - 2026-07-22

    # If there were any (positive) contribution transactions in the original instruction, we need to delete the
    # contribution transactions that were created to reverse that payment and re-incur it. We assume that
    # multiple reversals have not been made for the same membership on the same date.
    for ct in ContributionTransaction.objects.filter(settlement=reversal.instruction, price__gt=0):
        # Delete the reversal ContributionTransactions that were created when the reversal was processed.
        ContributionTransaction.objects.filter(
            Q(price=-ct.price) | Q(price=ct.price),
            date=rt.date,
            person=ct.person, membership=ct.membership,
        ).delete()

    # Then, delete the ReversalTransaction that re-incurred the costs of the original direct debit to the personal tab.
    rt.delete()

    # Finally, delete the entire Reversal.
    reversal.delete()


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


def edit_amendment(amendment, date, iban, bic, reason):
    """
    Edit an unsent amendment to an authorization.

    Make sure you call this method only from within a database transaction!
    Make sure you call this method only for amendments that have not yet been sent to the bank!
    """
    other_bank = bic != amendment.authorization.bic
    amendment.date = date
    amendment.other_bank = other_bank
    amendment.reason = reason
    amendment.save()

    amendment.authorization.iban = iban
    amendment.authorization.bic = bic
    amendment.authorization.save()

    return amendment


def delete_amendment(amendment):
    """
    Delete an unsent amendment to an authorization.

    Make sure you call this method only from within a database transaction!

    Make sure you call this method only for amendments that have not yet been sent to the bank!
    """

    amendment.authorization.iban = amendment.previous_iban
    amendment.authorization.bic = amendment.previous_bic
    amendment.authorization.save()

    amendment.delete()

    return

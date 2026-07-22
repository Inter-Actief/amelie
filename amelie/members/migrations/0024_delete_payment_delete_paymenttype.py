# Written by Kevin Alberts <kevin.alberts@inter-actief.net> on 2026-07-23
import datetime
from datetime import timezone as tz
import logging
from decimal import Decimal

from django.db import migrations
from django.db.models import Model
from django.utils import timezone, translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Based on Person.incomplete_name method
def incomplete_name(person):
    first_name = person.first_name
    if not person.first_name and person.initials:
        first_name = person.initials
    if person.last_name_prefix:
        return ' '.join([first_name, person.last_name_prefix, person.last_name])
    else:
        return ' '.join([first_name, person.last_name])


# Based on ManualPaymentSettlement.create_settlement_for_transactions method.
def create_settlement_for_transactions(ManualPaymentSettlement, SettlementManualPaymentTransaction,
                                       transactions, payment_method, person, description,
                                       payment_datetime, created_by=None):
    transactions = list(transactions)
    if not transactions:
        raise ValueError("No transactions given! Cannot create an empty manual payment")

    # Calculate the total settlement amount
    total_transactions_price = sum(t.price for t in transactions) or Decimal("0.00")

    # Create a ManualPayment settlement with the given payment method.
    settlement = ManualPaymentSettlement.objects.create(
        payment_date=payment_datetime.date(),
        payment_method=payment_method,
        description=description[:140],
        person=person,
        amount=total_transactions_price,
        created_by=created_by
    )

    # Save the settlement reference in all transactions
    for transaction in transactions:
        transaction.settlement = settlement
        transaction.save()

    # If transactions come out to a non-zero amount, add a SettlementManualPaymentTransaction for
    # the total transaction amount to cancel out the balance of those transactions
    if total_transactions_price != 0:
        settlement_transaction = SettlementManualPaymentTransaction(
            date=payment_datetime, price=-total_transactions_price, person=person,
            description=description[:200], settlement=settlement
        )
        settlement_transaction.save()
        # Register this manual payment as the payment transaction for the settlement
        settlement.manual_payment_transaction = settlement_transaction
        settlement.save()
    return settlement


def membership_type_name(person, membership_type):
    language = person.preferred_language
    if language == "en" and membership_type.name_en:
        return membership_type.name_en
    else:
        return membership_type.name_nl


def forwards(apps, schema_editor):
    """
    Create ContributionTransactions for all memberships that do not have one,
    and add a Manual Payments for all memberships that have a Payment that is not direct debit.
    """
    Membership = apps.get_model('members', 'Membership')
    PaymentType = apps.get_model('members', 'PaymentType')
    ManualPaymentSettlement = apps.get_model('personal_tab', 'ManualPaymentSettlement')
    ContributionTransaction = apps.get_model('personal_tab', 'ContributionTransaction')
    ReversalTransaction = apps.get_model('personal_tab', 'ReversalTransaction')
    SettlementManualPaymentTransaction = apps.get_model('personal_tab', 'SettlementManualPaymentTransaction')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')
    logger.info(f'Creating ContributionTransactions and Manual Payments for any unpaid memberships and memberships that were not paid by Authorization...')
    try:
        internal_settlement_payment_method = PaymentMethod.objects.get(name_en='Internal settlement')
        logger.info(f'Using existing Internal settlement payment method with PK "{internal_settlement_payment_method.pk}"...')
    except PaymentMethod.DoesNotExist:
        # No Internal settlement payment type exists, but we need one to link any settlements for reversed contributions to. Create one.
        internal_settlement_payment_method = PaymentMethod.objects.create(
            name_en="Internal settlement",
            name_nl="Interne verrekening",
            description_en="Internal settlement. These transactions cancel each other out to a zero balance.",
            description_nl="Interne verrekening. Deze transacties zijn met elkaar verrekend tot een nulbalans.",
            visible=True, visible_memberships=False, visible_activities=False
        )
        logger.info(f'No Internal settlement payment type existed. Created a new one with PK "{internal_settlement_payment_method.pk}"...')
    try:
        pre_sepa_payment_method = PaymentMethod.objects.get(name_en='Pre-SEPA')
        logger.info(f'Using existing Pre-SEPA payment method with PK "{pre_sepa_payment_method.pk}"...')
    except PaymentMethod.DoesNotExist:
        # No Pre-SEPA payment type exists, but we need one to link the new manual payment settlement to. Create one.
        pre_sepa_payment_method = PaymentMethod.objects.create(
            name_en="Pre-SEPA",
            name_nl="Pre-SEPA",
            description_en="Pre-SEPA payment. This payment was made before the introduction of SEPA authorizations.",
            description_nl="Pre-SEPA-betaling. Deze betaling is gedaan voor de introductie van SEPA-machtigingen.",
            visible=False, visible_memberships=False, visible_activities=False
        )
        logger.info(f'No Pre-SEPA payment type existed. Created a new one with PK "{pre_sepa_payment_method.pk}"...')

    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    pre_sepa_begin_date = datetime.date(2013, 10, 31)
    pre_sepa_transaction_date = datetime.datetime(2013, 10, 30, 22, 59, 59, tzinfo=tz.utc)

    # Create ContributionTransactions for all memberships that do not have one but need one,
    # and create a Manual Payments for the memberships that have been paid.
    membership_count = Membership.objects.count()
    num_cts_created = 0
    num_settlements_created = 0
    num_left_unpaid = 0
    created_internal_settlements = 0
    try:
        authorization_payment_type = PaymentType.objects.get(pk=4)  # Annual authorization
    except PaymentType.DoesNotExist:
        authorization_payment_type = None
    for i, membership in enumerate(Membership.objects.all().order_by('pk')):
        # Translate any description strings to the user's preferred language
        with translation.override(membership.member.preferred_language):
            # If this concerns a paid membership (free memberships don't need any transactions)
            if membership.type.price != 0:
                if i % 1000 == 0:
                    logger.info(f'- [{i}/{membership_count}] Processing ID {membership.pk}...')
                # ContributionTransactions need to be created for memberships that:
                if (
                    # - Are not paid and currently have no positive ContributionTransaction without a settlement
                    (not hasattr(membership, 'payment') and not membership.contributiontransaction_set.filter(price__gt=0, settlement=None).exists())
                    or
                    # - Are paid with a payment type that is not Authorization (manual payments)
                    (hasattr(membership, 'payment') and membership.payment.payment_type != authorization_payment_type)
                    or
                    # - Are paid with an Authorization, but has no positive ContributionTransaction
                    #   (if pre-sepa: that's ok, it will be marked paid later, if post-sepa: manually created authorization payment, wrong, will be left unpaid)
                    (hasattr(membership, 'payment') and membership.payment.payment_type == authorization_payment_type and not membership.contributiontransaction_set.filter(price__gt=0).exists())
                ):
                    # If this membership is paid, use the payment date as the date for the transaction, else, just guesstimate.
                    if hasattr(membership, 'payment') and membership.payment.date:
                        date = datetime.datetime.combine(
                            membership.payment.date, datetime.time(0, 0)
                        ).replace(tzinfo=timezone.get_default_timezone())
                    else:
                        # 1st of September in the year of the membership.
                        date = datetime.datetime(membership.year, 9, 1, 0, 0, 0, tzinfo=tz.utc)

                    # Create the contributiontransaction
                    ct = ContributionTransaction(
                        date=date, price=membership.type.price, person=membership.member,
                        membership=membership, settlement=None,
                        description=_("Contribution {membership_type} ({begin_year}/{end_year})").format(
                            membership_type=membership_type_name(membership.member, membership.type),
                            begin_year=membership.year,
                            end_year=(membership.year + 1)
                        )
                    )
                    ct.save()
                    num_cts_created += 1

                # Negative ContributionTransactions should cancel out against a positive ReversalTransaction on the same date.
                # If any unpaid negative transactions exist, find their corresponding Reversal and make a settlement so they are marked as paid.
                unpaid_negative_transactions = membership.contributiontransaction_set.filter(price__lt=0, settlement=None)
                for unpaid_negative_transaction in unpaid_negative_transactions:
                    # Try to find the corresponding unpaid ReversalTransaction
                    try:
                        reversal = ReversalTransaction.objects.get(
                            date=unpaid_negative_transaction.date,
                            price=-unpaid_negative_transaction.price,
                            person=unpaid_negative_transaction.person,
                            settlement=None
                        )
                    except ReversalTransaction.DoesNotExist:
                        # Give up, either the reversal was already settled against something else or this is a different
                        # situation all together. The negative transaction will remain unpaid in the personal tab.
                        logger.info(f'  - Membership {membership.pk} - Cannot find reversal for transaction {unpaid_negative_transaction.pk} ({unpaid_negative_transaction.price}) "{unpaid_negative_transaction.description}".')
                        continue
                    except ReversalTransaction.MultipleObjectsReturned:
                        # Give up, somehow there are multiple reversals on the exact same datetime.
                        # The negative transaction will remain unpaid in the personal tab.
                        logger.info(f'  - Membership {membership.pk} - Found multiple reversals for transaction {unpaid_negative_transaction.pk} ({unpaid_negative_transaction.price}) "{unpaid_negative_transaction.description}".')
                        continue

                    # Create a settlement that will cancel out the two transactions
                    logger.info(f'  - Membership {membership.pk} - Cancelling transaction {unpaid_negative_transaction.pk} ({unpaid_negative_transaction.price}) against {reversal.pk} ({reversal.price}).')
                    create_settlement_for_transactions(
                        ManualPaymentSettlement,
                        SettlementManualPaymentTransaction,
                        transactions=[unpaid_negative_transaction, reversal],
                        payment_method=internal_settlement_payment_method,
                        person=membership.member,
                        description=_("Internal settlement for reversed contribution {membership_type} ({begin_year}/{end_year}) (migrated)").format(
                            membership_type=membership_type_name(membership.member, membership.type),
                            begin_year=membership.year, end_year=(membership.year + 1)
                        ),
                        payment_datetime=unpaid_negative_transaction.date,
                        created_by=None
                    )
                    created_internal_settlements += 1

                # If a payment exists for this membership, add any unpaid positive transactions to a ManualPayment.
                # (the negative transactions cross off against positive ReversalTransactions that are not linked to the contribution)
                if hasattr(membership, 'payment') and membership.payment.payment_type != authorization_payment_type:
                    unpaid_transactions = membership.contributiontransaction_set.filter(price__gt=0, settlement=None)
                    if unpaid_transactions.exists():
                        # Must exist due to being created in migration personal_tab.0014_personaltabsettlement_and_more
                        payment_method = PaymentMethod.objects.get(name_en=membership.payment.payment_type.name)
                        if membership.payment.date:
                            transaction_date = datetime.datetime.combine(
                                membership.payment.date, datetime.time(0, 0)
                            ).replace(tzinfo=timezone.get_default_timezone())
                        else:
                            # 1st of September in the year of the membership.
                            transaction_date = datetime.datetime(
                                membership.year, 9, 1, 0, 0, 0, tzinfo=tz.utc
                            )
                        # Create a ManualPayment settlement with the same payment method as the old Payment.
                        create_settlement_for_transactions(
                            ManualPaymentSettlement,
                            SettlementManualPaymentTransaction,
                            transactions=unpaid_transactions,
                            payment_method=payment_method,
                            person=membership.member,
                            description=_("Manual payment for contribution {membership_type} ({begin_year}/{end_year}) (migrated)").format(
                                membership_type=membership_type_name(membership.member, membership.type),
                                begin_year=membership.year, end_year=(membership.year + 1)
                            ),
                            payment_datetime=transaction_date,
                            created_by=None
                        )
                        num_settlements_created += 1
                # If the membership was paid with Annual Authorization, but an unpaid ContributionTransaction exists,
                # then EITHER that payment was created manually after the Pre-SEPA date and is wrong. It needs to remain unpaid.
                #      OR it was created BEFORE the Pre-SEPA date, and it is an old transaction. It needs to be marked paid with the Pre-SEPA method.
                elif hasattr(membership, 'payment') and membership.payment.payment_type == authorization_payment_type:
                    unpaid_transactions = membership.contributiontransaction_set.filter(price__gt=0, settlement=None)
                    if unpaid_transactions.exists():
                        # Check if pre-sepa
                        date = membership.payment.date or datetime.date(membership.year, 9, 1)
                        if date < pre_sepa_begin_date:
                            # Correct, needs to be marked as paid
                            if membership.payment.date:
                                transaction_date = datetime.datetime.combine(
                                    membership.payment.date, datetime.time(0, 0)
                                ).replace(tzinfo=timezone.get_default_timezone())
                            else:
                                # Use the pre-sepa transaction date.
                                transaction_date = pre_sepa_transaction_date
                            # Create a ManualPayment settlement with the Pre-SEPA payment method.
                            create_settlement_for_transactions(
                                ManualPaymentSettlement,
                                SettlementManualPaymentTransaction,
                                transactions=unpaid_transactions,
                                payment_method=pre_sepa_payment_method,
                                person=membership.member,
                                description=_("Pre-SEPA payment for contribution {membership_type} ({begin_year}/{end_year}) (migrated)").format(
                                    membership_type=membership_type_name(membership.member, membership.type),
                                    begin_year=membership.year, end_year=(membership.year + 1)
                                ),
                                payment_datetime=transaction_date,
                                created_by=None
                            )
                            num_settlements_created += 1
                    else:
                        # Manually created after the pre-sepa date. Needs to be left unpaid.
                        num_left_unpaid += 1
                else:
                    num_left_unpaid += 1
    logger.info(f'- [DONE] Created {num_cts_created} ContributionTransactions, {num_settlements_created} settlements, settled {created_internal_settlements} reversals and left {num_left_unpaid} memberships unpaid.')


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0023_documenso_id_signed_document'),
        ('personal_tab', '0014_personaltabsettlement_and_more'),
    ]

    operations = [
        # Create ContributionTransactions for all memberships that do not have one,
        # and add a Manual Payments for all memberships that have a Payment that is not direct debit.
        migrations.RunPython(forwards),
        migrations.DeleteModel(
            name='Payment',
        ),
        migrations.DeleteModel(
            name='PaymentType',
        ),
    ]

# Written by Kevin Alberts <kevin.alberts@inter-actief.net> on 2026-07-23
import datetime
from datetime import timezone as tz
import logging
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


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
def create_settlement_for_transactions(ManualPaymentSettlement, ManualPaymentSettlementTransaction,
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

    # If transactions come out to a non-zero amount, add a ManualPaymentSettlementTransaction for
    # the total transaction amount to cancel out the balance of those transactions
    if total_transactions_price != 0:
        settlement_transaction = ManualPaymentSettlementTransaction(
            date=payment_datetime, price=-total_transactions_price, person=person,
            description=description[:200], settlement=settlement
        )
        settlement_transaction.save()
    return settlement


def forwards(apps, schema_editor):
    """
    Create ContributionTransactions for all memberships that do not have one,
    and add a Manual Payments for all memberships that have a Payment that is not direct debit.
    """
    Membership = apps.get_model('members', 'Membership')
    PaymentType = apps.get_model('members', 'PaymentType')
    ManualPaymentSettlement = apps.get_model('personal_tab', 'ManualPaymentSettlement')
    ContributionTransaction = apps.get_model('personal_tab', 'ContributionTransaction')
    ManualPaymentSettlementTransaction = apps.get_model('personal_tab', 'ManualPaymentSettlementTransaction')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')
    logger.info(f'Creating ContributionTransactions and Manual Payments for any unpaid memberships and memberships that were not paid by Authorization...')

    # Create ContributionTransactions for all memberships that do not have one but need one,
    # and create a Manual Payments for the memberships that have been paid.
    membership_count = Membership.objects.count()
    num_cts_created = 0
    num_settlements_created = 0
    num_left_unpaid = 0
    try:
        authorization_payment_type = PaymentType.objects.get(pk=4)  # Annual authorization
    except PaymentType.DoesNotExist:
        authorization_payment_type = None
    for i, membership in enumerate(Membership.objects.all()):
        # If this concerns a paid membership (free memberships don't need any transactions)
        if membership.type.price != 0:
            if i % 1000 == 0:
                logger.info(f'- [{i}/{membership_count}] Processing {membership.member.first_name} {membership.member.last_name}...')
            # ContributionTransactions need to be created for memberships that:
            if (
                # - Are not paid and currently have no ContributionTransaction with no settlement
                (not hasattr(membership, 'payment') and not membership.contributiontransaction_set.filter(settlement=None).exists())
                or
                # - Are paid with a payment type that is not Authorization (manual payments)
                (hasattr(membership, 'payment') and membership.payment.payment_type != authorization_payment_type)
                or
                # - Are paid with an Authorization, but has no ContributionTransaction
                (hasattr(membership, 'payment') and membership.payment.payment_type != authorization_payment_type)
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
                    date=date, price=membership.type.price, person=membership.member, membership=membership, settlement=None,
                    description='Contribution {membership_type} ({begin_year}/{end_year})'.format(
                        membership_type=membership.type.name_en,
                        begin_year=membership.year,
                        end_year=(membership.year + 1)
                    )
                )
                ct.save()
                num_cts_created += 1

            # If a payment exists for this membership, add any unpaid transactions to a ManualPayment.
            if hasattr(membership, 'payment'):
                unpaid_transactions = membership.contributiontransaction_set.filter(settlement=None)
                if unpaid_transactions.exists():
                    # Must exist due to being created in migration personal_tab.0014_personaltabsettlement_and_more
                    payment_method = PaymentMethod.objects.get(name=membership.payment.payment_type.name)
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
                        ManualPaymentSettlementTransaction,
                        transactions=unpaid_transactions,
                        payment_method=payment_method,
                        person=membership.member,
                        description="Payment on {date} for contribution {membership_type} ({begin_year}/{end_year})".format(
                            date=membership.payment.date, membership_type=membership.type.name_en,
                            begin_year=membership.year, end_year=(membership.year + 1)
                        ),
                        payment_datetime=transaction_date,
                        created_by=None
                    )
                    num_settlements_created += 1
            else:
                num_left_unpaid += 1
    logger.info(f'- [DONE] Created {num_cts_created} ContributionTransactions, {num_settlements_created} settlements and left {num_left_unpaid} memberships unpaid.')


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

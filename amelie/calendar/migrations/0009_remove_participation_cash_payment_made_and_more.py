# Written by Kevin Alberts <kevin.alberts@inter-actief.net> on 2026-07-21

import logging
from decimal import Decimal

from django.db import migrations

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# This is a huge pain in the butt, because it's in a migration
# so we can't use any of the helper functions on the models...

# Based on Participation.calculate_costs method (and underlying methods)
def calculate_costs(apps, participation):
    # List of extra costs per enrollment option
    prices_extra = []
    for enrollment_option_answer in participation.enrollmentoptionanswer_set.all():
        price_extra = Decimal(0)

        # Checkbox answers
        if hasattr(enrollment_option_answer, 'enrollmentoptioncheckboxanswer'):
            enrollment_option_answer = enrollment_option_answer.enrollmentoptioncheckboxanswer
            if enrollment_option_answer.answer:
                price_extra = enrollment_option_answer.enrollmentoption.enrollmentoptioncheckbox.price_extra
            prices_extra.append(price_extra)
            continue

        # Numeric answers
        if hasattr(enrollment_option_answer, 'enrollmentoptionnumericanswer'):
            enrollment_option_answer = enrollment_option_answer.enrollmentoptionnumericanswer
            price_extra = enrollment_option_answer.enrollmentoption.enrollmentoptionnumeric.price_extra * enrollment_option_answer.answer
            prices_extra.append(price_extra)
            continue

        # Selectbox answers
        if hasattr(enrollment_option_answer, 'enrollmentoptionselectboxanswer'):
            enrollment_option_answer = enrollment_option_answer.enrollmentoptionselectboxanswer
            price_extra = enrollment_option_answer.answer.price_extra
            prices_extra.append(price_extra)
            continue

        # Food answers
        if hasattr(enrollment_option_answer, 'enrollmentoptionfoodanswer'):
            enrollment_option_answer = enrollment_option_answer.enrollmentoptionfoodanswer
            if enrollment_option_answer.dishprice:
                price_extra = enrollment_option_answer.dishprice.price
            prices_extra.append(price_extra)
            continue

        # Question answers
        if hasattr(enrollment_option_answer, 'enrollmentoptionquestionanswer'):
            # Questions never have extra price.
            prices_extra.append(price_extra)
            continue

        raise ValueError(f"Unknown enrollment option answer class: ID {enrollment_option_answer.pk} {enrollment_option_answer.__class__.__name__}")

    # Calculate and return total costs, and if there were any additional costs due to enrollment options.
    total_costs = participation.event.activity.price + sum(prices_extra)
    return total_costs, len(prices_extra) > 0


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
    """Convert any old cash payments for activity participation to Personal Tab ActivityTransactions."""
    Participation = apps.get_model('calendar', 'Participation')
    ActivityTransaction = apps.get_model('personal_tab', 'ActivityTransaction')
    ManualPaymentSettlement = apps.get_model('personal_tab', 'ManualPaymentSettlement')
    ManualPaymentSettlementTransaction = apps.get_model('personal_tab', 'ManualPaymentSettlementTransaction')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')

    all_participations_count = Participation.objects.all().count()
    cash_participations = Participation.objects.filter(payment_method='C')
    cash_participation_count = cash_participations.count()
    unpaid_cash_participation_count = Participation.objects.filter(payment_method='C', cash_payment_made=False).count()
    logger.info('Migrating unpaid cash payments for activity participation to personal tab ActivityTransactions...')
    logger.info('Total unpaid cash: {}, total cash: {}, total participations: {}'.format(
        unpaid_cash_participation_count, cash_participation_count, all_participations_count
    ))
    try:
        cash_payment_method = PaymentMethod.objects.get(name='Cash')
        logger.info(f'Using existing Cash payment method with PK "{cash_payment_method.pk}...')
    except PaymentMethod.DoesNotExist:
        # No cash payment type exists, but we need one to link the new manual payment settlement to. Create one.
        cash_payment_method = PaymentMethod.objects.create(
            name="Cash",
            description="Cash payment. Money goes into the brown cashbox and the payment is written down on the brown cashbox list with the student number.",
            visible=True,
        )
        logger.info(f'No cash payment type existed. Created a new one with PK "{cash_payment_method.pk}...')
    for i, participation in enumerate(cash_participations):
        # ActivityTransaction creation code below adapted from
        # `personal_tab.transactions.participation_transaction` as it was on 2026-07-21.

        # Take the beginning date/time as the date of the transaction.
        price, with_enrollment_options = calculate_costs(apps=apps, participation=participation)
        logger.info(f'- [{i+1}/{cash_participation_count}] {participation.id} - {incomplete_name(participation.person)} for {participation.event.summary_en} on {participation.event.begin.date()}')

        # Create the new ActivityTransaction.
        activity_transaction = ActivityTransaction.objects.create(
            price=price,
            description=f"Migrated old cash payments for enrollment to {participation.event.summary_en} on {participation.event.begin.date()}",
            participation=participation,
            event=participation.event,
            person=participation.person,
            date=participation.event.begin,
            with_enrollment_options=with_enrollment_options,
            added_by=participation.added_by,
        )

        if participation.cash_payment_made:
            # Also create a counterbalancing settlement payment, because the original payment was already made.
            create_settlement_for_transactions(
                ManualPaymentSettlement,
                ManualPaymentSettlementTransaction,
                transactions=[activity_transaction],
                payment_method=cash_payment_method,
                person=participation.person,
                description=f"Cash payment for enrollment to {participation.event.summary_en} on {participation.event.begin.date()}",
                payment_datetime=participation.event.begin,
                created_by=participation.added_by,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0008_alter_event_participants'),
        ('personal_tab', '0014_personaltabsettlement_and_more'),
        ('activities', '0013_activity_enrollment_private')
    ]

    operations = [
        # Convert any old unpaid cash payments for activity participation to Personal Tab transactions.
        migrations.RunPython(forwards),
        migrations.RemoveField(
            model_name='participation',
            name='cash_payment_made',
        ),
        migrations.RemoveField(
            model_name='participation',
            name='payment_method',
        ),
    ]

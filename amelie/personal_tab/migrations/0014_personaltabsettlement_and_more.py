# Written by Kevin Alberts <kevin.alberts@inter-actief.net> on 2026-07-20
import datetime
from datetime import timezone as tz
import logging
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def import_payment_methods_forwards(apps, schema_editor):
    """Copy each old members.PaymentType into personal_tab.PaymentMethod, preserving PKs."""
    PaymentType = apps.get_model('members', 'PaymentType')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')

    logger.info('Migrating old members.PaymentType to new personal_tab.PaymentMethod...')
    total_count = PaymentType.objects.count()
    for i, old in enumerate(PaymentType.objects.all()):
        logger.info(f'- [{i+1}/{total_count}] Processing {old.name}...')
        # Create the new inherited DebtCollectionInstruction, re-using the same ID.
        PaymentMethod.objects.create(
            id=old.id,
            name=old.name,
            description=old.description,
            visible=old.visible
        )


def import_payment_methods_backwards(apps, schema_editor):
    """Reverse: Delete all PaymentMethods"""
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')
    PaymentMethod.objects.all().delete()


def migrate_debt_collection_instructions_forwards(apps, schema_editor):
    """Copy each old DebtCollectionInstruction into PersonalTabSettlement + new DebtCollectionInstruction, preserving PKs."""
    OldDebtCollectionInstruction = apps.get_model('personal_tab', 'OldDebtCollectionInstruction')
    DebtCollectionInstruction = apps.get_model('personal_tab', 'DebtCollectionInstruction')

    logger.info('Migrating old debt collections to new model...')
    total_count = OldDebtCollectionInstruction.objects.count()
    for i, old in enumerate(OldDebtCollectionInstruction.objects.all()):
        if i % 1000 == 0:
            logger.info(f'- [{i}/{total_count}] Processing ID {old.id}...')
        # Create the new inherited DebtCollectionInstruction, re-using the same ID.
        DebtCollectionInstruction.objects.create(
            id=old.id,
            description=old.description,
            amount=old.amount,
            end_to_end_id=old.end_to_end_id,
            amendment=old.amendment,
            authorization=old.authorization,
            batch=old.batch,
        )


def migrate_debt_collection_instructions_backwards(apps, schema_editor):
    """Reverse: flatten PersonalTabSettlement + DebtCollectionInstruction back into a single table."""
    DebtCollectionInstruction = apps.get_model('personal_tab', 'DebtCollectionInstruction')
    OldDebtCollectionInstruction = apps.get_model('personal_tab', 'OldDebtCollectionInstruction')

    logger.info('Reverting new debt collections to old model...')
    for dci in DebtCollectionInstruction.objects.all():
        logger.info(f'- {dci.id} - {dci.amount} eur')
        OldDebtCollectionInstruction.objects.create(
            id=dci.id,
            description=dci.description,  # comes from the parent via multi-table inheritance
            amount=dci.amount,  # comes from the parent via multi-table inheritance
            end_to_end_id=dci.end_to_end_id,
            amendment=dci.amendment,
            authorization=dci.authorization,
            batch=dci.batch,
        )


def incomplete_name(person):
    first_name = person.first_name
    if not person.first_name and person.initials:
        first_name = person.initials
    if person.last_name_prefix:
        return ' '.join([first_name, person.last_name_prefix, person.last_name])
    else:
        return ' '.join([first_name, person.last_name])


def create_manual_batch_for_pre_sepa_transactions_forwards(apps, scheme_editor):
    Person = apps.get_model('members', 'Person')
    Transaction = apps.get_model('personal_tab', 'Transaction')
    ManualPaymentSettlement = apps.get_model('personal_tab', 'ManualPaymentSettlement')
    ManualPaymentSettlementTransaction = apps.get_model('personal_tab', 'ManualPaymentSettlementTransaction')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')
    logger.info(f'Create a manual payment settlements for any transactions from before the SEPA debt collections came into effect....')
    try:
        pre_sepa_payment_method = PaymentMethod.objects.get(name='Pre-SEPA')
        logger.info(f'Using existing Pre-SEPA payment method with PK "{pre_sepa_payment_method.pk}...')
    except PaymentMethod.DoesNotExist:
        # No cash payment type exists, but we need one to link the new manual payment settlement to. Create one.
        pre_sepa_payment_method = PaymentMethod.objects.create(
            name="Pre-SEPA",
            description="Pre-SEPA payment. This payment was made before the introduction of SEPA authorizations.",
            visible=False,
        )
        logger.info(f'No Pre-SEPA payment type existed. Created a new one with PK "{pre_sepa_payment_method.pk}...')

    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    begin_date = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=tz.utc)
    transaction_date = datetime.datetime(2013, 10, 30, 22, 59, 59, tzinfo=tz.utc)
    # Get all the pre-SEPA transactions that have not been settled
    pre_sepa_transactions = Transaction.objects.filter(settlement=None, date__lt=begin_date)

    # Group by person
    people = pre_sepa_transactions.filter(person__isnull=False).order_by('person').distinct().values('person')
    people_count = len(people)
    for i, p in enumerate(people):
        person = Person.objects.get(id=p['person'])
        person_name = incomplete_name(person)
        transactions = pre_sepa_transactions.filter(person=person)
        logger.info(f'- [{i+1}/{people_count}] {person_name} - {transactions.count()} pre-SEPA transactions...')

        # Create a settlement payment to mark the old transactions as paid on the SEPA introduction date.
        create_settlement_for_transactions(
            ManualPaymentSettlement,
            ManualPaymentSettlementTransaction,
            transactions=transactions,
            payment_method=pre_sepa_payment_method,
            person=person,
            description=f"Settlement for transactions handled before SEPA debits were introduced - {person_name}",
            payment_datetime=transaction_date,
            created_by=None
        )


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0023_documenso_id_signed_document'),
        ('personal_tab', '0013_authorization_documenso_id_and_more'),
    ]

    operations = [
        # Create the new PaymentMethod model.
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20, unique=True, verbose_name='Name')),
                ('description', models.TextField(verbose_name='Description')),
                ('visible', models.BooleanField(default=True, verbose_name='Visible')),
                ('frontend_icon_name', models.CharField(blank=True, max_length=20, null=True, verbose_name='Icon name for frontend')),
            ],
            options={
                'verbose_name': 'payment method',
                'verbose_name_plural': 'payment methods',
                'ordering': ['description'],
            },
        ),

        # Create PaymentMethod instances from existing PaymentType instances.
        migrations.RunPython(import_payment_methods_forwards, import_payment_methods_backwards),

        # Create the new PersonalTabSettlement parent model.
        migrations.CreateModel(
            name='PersonalTabSettlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=140, validators=[django.core.validators.RegexValidator(message='Only alphanumerical signs are allowed', regex="^[a-zA-Z0-9-?:().,\\'+ ]*$")], verbose_name='description')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='amount')),
            ],
            options={
                'verbose_name': 'personal tab settlement',
                'verbose_name_plural': 'personal tab settlements',
                'ordering': ['pk'],
            },
        ),

        # Create the new ManualPaymentSettlement sibling model (no data to migrate)
        migrations.CreateModel(
            name='ManualPaymentSettlement',
            fields=[
                ('personaltabsettlement_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='personal_tab.personaltabsettlement')),
                ('payment_date', models.DateField(verbose_name='payment date')),
                ('person', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                             to='members.person', verbose_name='person')),
                ('payment_method', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                     to='personal_tab.paymentmethod', verbose_name='Payment method')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                                 related_name='+', to='members.person', verbose_name='Created by'))
            ],
            options={
                'verbose_name': 'manual payment settlement',
                'verbose_name_plural': 'manual payment settlements',
                'ordering': ['-payment_date', '-person', '-id'],
            },
            bases=('personal_tab.personaltabsettlement',),
        ),

        # Rename the old DebtCollectionInstruction so the new one can take its name.
        migrations.RenameModel('DebtCollectionInstruction', 'OldDebtCollectionInstruction'),

        # 4. Create the new DebtCollectionInstruction inheriting from PersonalTabSettlement.
        migrations.CreateModel(
            name='DebtCollectionInstruction',
            fields=[
                ('personaltabsettlement_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='personal_tab.personaltabsettlement')),
                ('end_to_end_id', models.CharField(max_length=35, validators=[
                    django.core.validators.RegexValidator(message='Only alphanumerical signs are allowed',
                                                          regex="^[a-zA-Z0-9-?:().,\\'+ ]*$")],
                                                   verbose_name='end-to-end-id')),
                ('amendment', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                                   related_name='instruction', to='personal_tab.amendment',
                                                   verbose_name='amendment')),
                ('authorization',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='instructions',
                                   to='personal_tab.authorization', verbose_name='mandate')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='instructions',
                                            to='personal_tab.debtcollectionbatch', verbose_name='batch')),
            ],
            options={
                'verbose_name': 'direct withdrawal-instruction',
                'verbose_name_plural': 'direct withdrawal-instructions',
                'ordering': ['batch', 'authorization'],
            },
            bases=('personal_tab.personaltabsettlement',),
        ),

        # Move the data over, preserving the original IDs.
        migrations.RunPython(migrate_debt_collection_instructions_forwards, migrate_debt_collection_instructions_backwards),

        # Re-point foreign keys on Transactions to point to PersonalTabSettlement.
        migrations.AlterField(
            model_name='transaction',
            name='debt_collection',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='transactions',
                to='personal_tab.personaltabsettlement',
                verbose_name='Settlement'
            ),
        ),

        # Rename Transaction.debt_collection foreign key to Transaction.settlement
        migrations.RenameField(
            model_name='transaction',
            old_name='debt_collection',
            new_name='settlement',
        ),

        # Re-point foreign keys on Reversals to point to the new DebtCollectionInstruction model.
        migrations.AlterField(
            model_name='reversal',
            name='instruction',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='reversal',
                to='personal_tab.debtcollectioninstruction',
                verbose_name='instruction'
            ),
        ),

        # Drop the old table.
        migrations.DeleteModel('OldDebtCollectionInstruction'),

        # Create new transaction models to support manual payments.
        migrations.CreateModel(
            name='ExtraManualPaymentTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='personal_tab.transaction')),
            ],
            bases=('personal_tab.transaction',),
        ),
        migrations.CreateModel(
            name='ManualPaymentSettlementTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='personal_tab.transaction')),
            ],
            bases=('personal_tab.transaction',),
        ),

        # Create a manual payment settlement for any transactions before the SEPA debt collections came into effect.
        # (2013-10-30, 23:00:00, tz.utc)
        migrations.RunPython(create_manual_batch_for_pre_sepa_transactions_forwards),
    ]

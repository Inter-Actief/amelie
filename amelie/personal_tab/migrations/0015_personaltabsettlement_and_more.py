# Written by Kevin Alberts <kevin.alberts@inter-actief.net> on 2026-07-20
import datetime
from datetime import timezone as tz
import logging
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
            description=description[:200], settlement=settlement, added_by=created_by
        )
        settlement_transaction.save()
        # Register this manual payment as the payment transaction for the settlement
        settlement.manual_payment_transaction = settlement_transaction
        settlement.save()
    return settlement


def import_payment_methods_forwards(apps, schema_editor):
    """Copy each old members.PaymentType into personal_tab.PaymentMethod, preserving PKs."""
    PaymentType = apps.get_model('members', 'PaymentType')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')

    logger.info('Migrating old members.PaymentType to new personal_tab.PaymentMethod...')
    total_count = PaymentType.objects.count()
    for i, old in enumerate(PaymentType.objects.all().order_by('pk')):
        logger.info(f'- [{i+1}/{total_count}] Processing {old.pk} - {old.name}...')
        # Create the new inherited DebtCollectionInstruction, re-using the same ID.
        PaymentMethod.objects.create(
            id=old.id,
            name_en=old.name,
            name_nl=old.name,
            description_en=old.description,
            description_nl=old.description,
            visible=old.visible,
            visible_memberships=old.visible,
            visible_activities=old.visible
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
    for i, old in enumerate(OldDebtCollectionInstruction.objects.all().order_by('pk')):
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
    SettlementManualPaymentTransaction = apps.get_model('personal_tab', 'SettlementManualPaymentTransaction')
    PaymentMethod = apps.get_model('personal_tab', 'PaymentMethod')
    logger.info(f'Create manual payment settlements for any transactions from before the SEPA debt collections came into effect....')
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
    begin_date = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=tz.utc)
    transaction_date = datetime.datetime(2013, 10, 30, 22, 59, 59, tzinfo=tz.utc)
    # Get all the pre-SEPA transactions that have not been settled
    pre_sepa_transactions = Transaction.objects.filter(settlement=None, date__lt=begin_date)

    # Group by person
    people = pre_sepa_transactions.filter(person__isnull=False).order_by('person').distinct().values('person')
    people_count = len(people)
    for i, p in enumerate(people):
        person = Person.objects.get(id=p['person'])
        # Translate any description strings to the user's preferred language
        with translation.override(person.preferred_language):
            person_name = incomplete_name(person)
            transactions = pre_sepa_transactions.filter(person=person)
            logger.info(f'- [{i+1}/{people_count}] {person_name} - {transactions.count()} pre-SEPA transactions...')

            # Create a settlement payment to mark the old transactions as paid on the SEPA introduction date.
            description = _("Settlement for transactions handled before SEPA debits were introduced - {person_name}").format(person_name=person_name)
            create_settlement_for_transactions(
                ManualPaymentSettlement,
                SettlementManualPaymentTransaction,
                transactions=transactions,
                payment_method=pre_sepa_payment_method,
                person=person,
                description=description,
                payment_datetime=transaction_date,
                created_by=None
            )


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0023_documenso_id_signed_document'),
        ('personal_tab', '0014_pendingregistertoken'),
    ]

    operations = [
        # Create the new PaymentMethod model.
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_en', models.CharField(max_length=20, unique=True, verbose_name='Name (EN)')),
                ('name_nl', models.CharField(max_length=20, unique=True, verbose_name='Name (NL)')),
                ('description_en', models.TextField(verbose_name='Description (EN)')),
                ('description_nl', models.TextField(verbose_name='Description (NL)')),
                ('visible', models.BooleanField(default=True, help_text="This payment method will be visible when creating a manual payment directly in someone's personal tab.", verbose_name='Visible')),
                ('visible_activities', models.BooleanField(default=True, help_text='This payment method will be visible when privileged members enter a manual payment for an activity.', verbose_name='Visible for activities')),
                ('visible_memberships', models.BooleanField(default=True, help_text='This payment method will be visible when privileged members enter a manual payment for a membership.', verbose_name='Visible for memberships')),
                ('frontend_icon_name', models.CharField(blank=True, max_length=20, null=True, verbose_name='Icon name for frontend')),
            ],
            options={
                'verbose_name': 'payment method',
                'verbose_name_plural': 'payment methods',
                'ordering': ['name_en', 'name_nl']
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

        # Create new transaction models to support manual settlements.
        migrations.CreateModel(
            name='SettlementExtraBalanceTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='personal_tab.transaction')),
            ],
            bases=('personal_tab.transaction',),
        ),
        migrations.CreateModel(
            name='SettlementManualPaymentTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='personal_tab.transaction')),
            ],
            bases=('personal_tab.transaction',),
        ),

        # Create the new ManualPaymentSettlement sibling model (no data to migrate)
        migrations.CreateModel(
            name='ManualPaymentSettlement',
            fields=[
                ('personaltabsettlement_ptr', models.OneToOneField(
                    auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                    primary_key=True, serialize=False, to='personal_tab.personaltabsettlement')
                 ),
                ('payment_date', models.DateField(verbose_name='payment date')),
                ('person', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    to='members.person', verbose_name='person')
                 ),
                ('payment_method', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='personal_tab.paymentmethod', verbose_name='Payment method')
                 ),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='+', to='members.person', verbose_name='Created by')
                 ),
                ('extra_balance_transaction', models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT,
                    related_name='manual_settlement', to='personal_tab.settlementextrabalancetransaction')
                 ),
                ('manual_payment_transaction', models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT,
                    related_name='manual_settlement', to='personal_tab.settlementmanualpaymenttransaction')
                 )
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

        # Create a manual payment settlement for any transactions before the SEPA debt collections came into effect.
        # (2013-10-30, 23:00:00, tz.utc)
        migrations.RunPython(create_manual_batch_for_pre_sepa_transactions_forwards),

        # Edit ordering on Transactions so even if added on date is identical, newest transaction by PK is still shown first.
        migrations.AlterModelOptions(
            name='transaction',
            options={'ordering': ['-date', '-added_on', '-pk'], 'verbose_name': 'Transaction', 'verbose_name_plural': 'Transactions'},
        ),
    ]

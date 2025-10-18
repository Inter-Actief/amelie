# -*- coding: UTF-8 -*-

from django.conf import settings
from django.urls import reverse
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, post_save, post_delete
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy as _l
from localflavor.generic.models import BICField, IBANField

from amelie.claudia.tools import verify_instance
from amelie.members.models import Person, Membership, Committee
from amelie.personal_tab.managers import AuthorizationManager, DebtCollectionInstructionManager


class DiscountPeriod(models.Model):
    begin = models.DateTimeField(blank=False, verbose_name=_l('begin'))
    end = models.DateTimeField(blank=True, null=True, verbose_name=_l('end'))
    description_nl = models.CharField(max_length=200, blank=False, verbose_name=_l('description'))
    description_en = models.CharField(max_length=200, blank=True, verbose_name=_l('description (en)'))
    articles = models.ManyToManyField('Article', related_name='discount_periods', blank=True,
                                      verbose_name=_l('articles'))
    ledger_account_number = models.CharField(max_length=8, verbose_name=_l('ledger account'), default='2500')
    balance_account_number = models.CharField(max_length=8, verbose_name=_l('balance account number'), default='2500')

    @property
    def description(self):
        language = get_language()

        if language == "en" and self.description_en:
            return self.description_en
        else:
            return self.description_nl

    def __str__(self):
        return self.description

    class Meta:
        ordering = ['-begin', '-end']
        verbose_name = _l('discount offer')
        verbose_name_plural = _l("discount offers")


class Discount(models.Model):
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name=_l('amount'))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_l('date'))
    discount_period = models.ForeignKey(DiscountPeriod, blank=False, on_delete=models.PROTECT,
                                        verbose_name=_l('discount offer'))

    def __str__(self):
        return '{} ({})'.format(self.discount_period.description, self.amount)

    class Meta:
        ordering = ['-date']
        verbose_name = _l('discount')
        verbose_name_plural = _l("discounts")


class DiscountCredit(models.Model):
    """
    A transaction regarding credit for Discount transactions.
    This is used when someone gets credit for a certain action, or if this credit is used.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    discount_period:    The discount period for which this credit is valid.
    date:               The date (and time) on which the transaction took place.
    price:              The amount that this transaction is for. Positive is credit, negative is usage of the credit.
    person:             The person the transaction is for.
    description:        The description of the transaction.
    discount:           Links to the Discount object in which this credit is used.

    added_on:           The date and time on which this object was created.
    added_by:           The person that created this object.
    """

    discount_period = models.ForeignKey(DiscountPeriod, on_delete=models.PROTECT, verbose_name=_l('discount offer'))
    date = models.DateTimeField(default=timezone.now, verbose_name=_l('date'))
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name=_l('amount'))
    person = models.ForeignKey(Person, verbose_name=_l('person'), on_delete=models.PROTECT)
    description = models.CharField(max_length=200, blank=True, verbose_name=_l('description'))
    discount = models.OneToOneField(Discount, blank=True, null=True, default=None, verbose_name=_l('discount'), on_delete=models.PROTECT)

    added_on = models.DateTimeField(verbose_name=_l('added on'), auto_now_add=True)

    # '+' related_name makes sure no reverse relation is added to Person
    added_by = models.ForeignKey(Person, blank=True, null=True, related_name="+", verbose_name=_l('added by'), on_delete=models.PROTECT)

    class Meta:
        ordering = ['-date', '-added_on']
        verbose_name = _l('Discount balance')
        verbose_name_plural = _l("discount balances")

    def __str__(self):
        return '{} ({})'.format(self.description, self.price)


class Transaction(models.Model):
    """
    Represents a transaction and is meant to be subclassed.
    Does however exist on its own (is not abstract) so that we also have a Transaction.objects.
    This is easier for generating overviews and such.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    date:               The date (and time) on which the transaction took place.
    price:              The price that this transaction is for.
    person:             The person this transaction is for.
    description:        The description of this transaction.
    discount:           Links to the Discount object in which this credit is used.
    debt_collection:    Links to the Debt Collection Entry on which this transaction was collected.

    added_on:           The date and time on which this object was created.
    added_by:           The person that created this object.
    """

    date = models.DateTimeField(default=timezone.now, verbose_name=_l('Date'))
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name=_l('Price'))
    person = models.ForeignKey(Person, verbose_name=_l('Person'), on_delete=models.PROTECT)
    description = models.CharField(max_length=200, blank=True, verbose_name=_l('Description'))
    discount = models.OneToOneField(Discount, blank=True, null=True, default=None, verbose_name=_l('discount'), on_delete=models.PROTECT)

    debt_collection = models.ForeignKey('DebtCollectionInstruction', verbose_name=_l('Direct withdrawal'), blank=True, null=True,
                                        related_name="transactions", on_delete=models.PROTECT)

    added_on = models.DateTimeField(verbose_name=_l('Added on'), auto_now_add=True)

    # '+' related_name makes sure no reverse relation is added to Person
    added_by = models.ForeignKey(Person, verbose_name=_l('Added by'), blank=True, null=True, related_name="+", on_delete=models.PROTECT)

    class Meta:
        ordering = ['-date', '-added_on']
        verbose_name = _l('Transaction')
        verbose_name_plural = _l("Transactions")

    def get_absolute_url(self):
        return reverse('personal_tab:transaction_detail', args=[self.pk])

    def __str__(self):
        return '{} ({})'.format(self.description, self.price)

    @property
    def editable(self):
        return False


class CustomTransaction(Transaction):
    """
    Transaction that does not belong anywhere else.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    @property
    def editable(self):
        return not self.debt_collection


class ActivityTransaction(Transaction):
    """
    Transaction to pay for an event.

    This is a relation to a specific Participation, but because this
    relation can also disappear when the person unenrolls for the event,
    there is also a 'backup-relation' with the event itself.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    event:                      The Event object this transaction belongs to.
    participation:              The Participation object this transaction belongs to.
                                Redundant with event, but can be empty.
    with_enrollment_options:    If the Participation has any enrollment options that might cost extra.
    """

    event = models.ForeignKey('calendar.Event', verbose_name=_l('Activities'), null=True, on_delete=models.SET_NULL)
    participation = models.ForeignKey('calendar.Participation', null=True, on_delete=models.SET_NULL,
                                      verbose_name=_l('Enrollment'))
    with_enrollment_options = models.BooleanField(verbose_name=_l('More sign up options'), default=False)

    def get_absolute_url(self):
        return reverse('personal_tab:activity_transaction_detail', args=[self.pk])


class CookieCornerTransaction(Transaction):
    """
    Transaction for the purchase of a product in the Cookie Corner.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    article: The Article that was bought.
    amount: The amount of this Article that were bought.
    """

    article = models.ForeignKey('Article', verbose_name=_l('Article'), null=True, on_delete=models.SET_NULL)
    amount = models.PositiveIntegerField(verbose_name=_l('Amount'))

    def kcal(self):
        if self.article.kcal is not None:
            return self.article.kcal * self.amount

    def get_absolute_url(self):
        return reverse('personal_tab:cookie_corner_transaction_detail', args=[self.pk])

    @property
    def editable(self):
        return not self.debt_collection


class AlexiaTransaction(Transaction):
    """
    Transaction for the purchase of a product via Alexia.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    transaction_id: The transaction ID of the transaction in Alexia.
    """

    transaction_id = models.PositiveIntegerField(verbose_name=_l('Transaction id'))

    def get_absolute_url(self):
        return reverse('personal_tab:alexia_transaction_detail', args=[self.pk])


class ContributionTransaction(Transaction):
    """
    Transaction for the payment of the contribution of a Membership.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.

    membership: The Membership object that is being paid with this transaction.
    """

    membership = models.ForeignKey(Membership, verbose_name=_l('Membership'), on_delete=models.PROTECT)


class LedgerAccount(models.Model):
    """
    Ledger account for an Article.

    Is used to group transactions.

    name:                   The name of the article.
    ledger_account_number:  The ledger account number of this article.
    """

    name = models.CharField(max_length=50, verbose_name=_l('Name'))

    ledger_account_number = models.CharField(max_length=8, verbose_name=_l('ledger account'), default='2500')

    default_statistics = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']
        verbose_name = _l('General ledger account')
        verbose_name_plural = _l("General ledger accounts")

    def __str__(self):
        return '{}'.format(self.name)


class Article(models.Model):
    """
    Article for in a CookieCornerTransaction. Can be everything, as long as it can be sold.

    name: The name of the article.
    category: The category the article will be placed in in the Cookie Corner.
    ledger_account: Link to the LedgerAccount that is used for this article.
    price: The price of the article.
    is_available: Indicates if the article is available at this moment. If it is False, the product cannot be sold.
    image: The image for the Cookie Corner to show in its interface. Optional.
    kcal: The amount of kiloCalories this product has. This is used in statistics. Optional.
    """

    name_nl = models.CharField(max_length=50, verbose_name=_l('Name'))
    name_en = models.CharField(max_length=50, verbose_name=_l('Name (en)'))
    category = models.ForeignKey('Category', verbose_name=_l('Category'), on_delete=models.PROTECT)
    ledger_account = models.ForeignKey(LedgerAccount, verbose_name=_l('General ledger account'), on_delete=models.PROTECT, related_name='articles')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price'))
    is_available = models.BooleanField(default=False, verbose_name=_l('Available'))
    image = models.ImageField(upload_to='cookie_corner', max_length=255, blank=False, verbose_name=_l('Image'))
    kcal = models.PositiveSmallIntegerField(verbose_name=_l('kCal'), blank=True, null=True)

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    class Meta:
        ordering = ['name_nl']
        verbose_name = _l('Article')
        verbose_name_plural = _l("Articles")

    def __str__(self):
        return '{}'.format(self.name)


class Category(models.Model):
    """
    A product belongs to a certain category. A category is mostly just a name.

    name: The name of the category.
    is_available: If the category is available. Same as Article.is_available.
    image: Image for the Cookie Corner. Same as Article.image.
    order: Integer indicating the order this category should be shown in. 1 will be shown before 2, etc.
    """

    name_nl = models.CharField(max_length=50, verbose_name=_l('Name'))
    name_en = models.CharField(max_length=50, verbose_name=_l('Name (en)'))
    is_available = models.BooleanField(default=False, verbose_name=_l('Available'))
    image = models.ImageField(upload_to='cookie_corner', max_length=255, blank=True, verbose_name=_l('Image'))
    order = models.PositiveIntegerField(default=0, null=False, verbose_name=_l('Sequence'))
    show_calculator_in_pos = models.BooleanField(default=False, verbose_name=_l('Show the calculator in the Point of Sale instead of the products'),
                                                 help_text=_l('The first active article in the category will be used for calculations.'))

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    def active_articles(self):
        return self.article_set.filter(is_available=True)

    class Meta:
        ordering = ['order', 'name_nl']
        verbose_name = _l('Category')
        verbose_name_plural = _l('Categories')

    def __str__(self):
        return '{}'.format(self.name)


class RFIDCard(models.Model):
    """
    Represents an RFID card which is unique and linked to a Person.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """

    # RFID types
    # Source: API Driver Manual of ACR120U Contactless Smart Card Reader
    # https://www.acs.com.hk/download-manual/428/API_ACR120U_v3.00.pdf
    TYPES = {'01': _l('Mifare Light'),
             '02': _l('Mifare 1K (Student card/Building card)'),
             '03': _l('Mifare 4K (Public transit card)'),
             '04': _l('Mifare DESFire'),
             '05': _l('Mifare Ultralight (Student card/IA keychain)'),
             '06': _l('JCOP30'),
             '07': _l('Shanghai Transport'),
             '08': _l('MPCOS Combi'),
             '80': _l('ISO Type B, Calypso'),
             '81': _l('ASK CTS256B, Type B'),
             '82': _l('ASK CTS521B, Type B'),
             }

    person = models.ForeignKey(Person, verbose_name=_l('Person'), on_delete=models.CASCADE)
    code = models.CharField(max_length=50, unique=True, verbose_name=_l('Rfid code'))
    active = models.BooleanField(default=False, verbose_name=_l('Activated'))
    last_used = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_l('Date last used'))
    created = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_l('Creation date'))

    class Meta:
        ordering = ['code']
        verbose_name = _l('RFID card')
        verbose_name_plural = _l('RFID cards')

    def __str__(self):
        if self.code[:3] == '02,':
            rfid_bytes = self.code[3:].split(':')
            rfid_bytes.reverse()
            number = int(''.join(rfid_bytes), 16)

            return '%s (%s)' % (self.code, number)
        else:
            return self.code

    @property
    def is_before_new_rfid_cards(self):
        return self.created.date() < settings.DATE_OLD_RFID_CARDS

    @property
    def used_before_new_rfid_cards(self):
        return self.last_used.date() < settings.DATE_OLD_RFID_CARDS


    def type(self):
        """Convert an RFID ID to a type, if possible."""

        result = None

        type_code = self.code[:2]
        if type_code in RFIDCard.TYPES:
            result = RFIDCard.TYPES[type_code]

        return result


SEPA_CHAR_VALIDATOR = RegexValidator(regex=r'^[a-zA-Z0-9-?:().,\'+ ]*$',
                                     message=_l('Only alphanumerical signs are allowed'))


class AuthorizationType(models.Model):
    """A kind of Authorization"""

    """Name of the authorization (Dutch)"""
    name_nl = models.CharField(max_length=50, verbose_name=_l('name'))

    """Name of the authorization (English)"""
    name_en = models.CharField(blank=True, max_length=50, verbose_name=_l('name (en)'))

    """Short description of the authorization (Dutch)"""
    text_nl = models.TextField(verbose_name=_l('text'))

    """Short description of the authorization (English)"""
    text_en = models.TextField(blank=True, verbose_name=_l('text (en)'))

    """An authorization of this type may be newly created and signed."""
    active = models.BooleanField(default=False, verbose_name=_l('active'))

    """Contribution payments may be collected using this authorization."""
    contribution = models.BooleanField(default=False, verbose_name=_l('membership fee'))

    """Consumption payments may be collected using this authorization."""
    consumptions = models.BooleanField(default=False, verbose_name=_l('consumptions'))

    """Activity payments may be collected using this authorization."""
    activities = models.BooleanField(default=False, verbose_name=_l('activities'))

    """Other payments may be collected using this authorization."""
    other_payments = models.BooleanField(default=False, verbose_name=_l('other payments'))

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    @property
    def text(self):
        language = get_language()

        if language == "en" and self.text_en:
            return self.text_en
        else:
            return self.text_nl

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        ordering = ['name_nl']
        verbose_name = _l('type of mandate')
        verbose_name_plural = _l('types of mandate')


class Authorization(models.Model):
    """
    Authorization for direct debits.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """

    """Prefix for authorization reference (machtigingskenmerk)"""
    PREFIX = 'IA-MNDT-'

    """Type of authorization"""
    authorization_type = models.ForeignKey(AuthorizationType, on_delete=models.PROTECT, verbose_name=_l('type'))

    """Person that gave the authorization"""
    person = models.ForeignKey(Person, verbose_name=_l('person'), null=True, blank=True, on_delete=models.PROTECT)

    """IBAN for authorization"""
    iban = IBANField(verbose_name=_l('IBAN'), blank=True)

    """BIC for authorization"""
    bic = BICField(verbose_name=_l('BIC'), blank=True)

    """Name of the account holder"""
    account_holder_name = models.CharField(max_length=70, verbose_name=_l('account holder'),
                                           validators=[SEPA_CHAR_VALIDATOR], blank=True)

    """Start date of the authorization"""
    start_date = models.DateField(verbose_name=_l('startdate'))

    """End date of the authorization, is None if the authorization has not ended yet."""
    end_date = models.DateField(verbose_name=_l('enddate'), null=True, blank=True)

    """This authorization has been signed"""
    is_signed = models.BooleanField(default=False, verbose_name=_l('has been signed'))

    objects = AuthorizationManager()

    def authorization_reference(self):
        """Gives the complete authorization reference with prefix"""
        return '%s%08d' % (Authorization.PREFIX, self.id)

    def is_active(self):
        """Indicates if this authorization is active.

        Active means signed and not ended."""
        return self.is_signed and not self.end_date

    def next_amendment(self):
        """
        Gives the amendment that has to be sent with the next debt collection instruction.

        Returns None if no amendment is present.
        """
        try:
            return self.amendments.get(instruction__isnull=True)
        except Amendment.DoesNotExist:
            return None

    def next_sequence_type(self):
        """
        Gives the sequence type for the next debt collection instruction.

        Returns DebtCollectionBatch.FRST or DebtCollectionBatch.RCUR depending on the previous
        debt collection instructions. Returns None if the sequence type cannot be determined yet
        because there is an ongoing FRST batch.
        """
        amendment = self.next_amendment()
        if amendment and amendment.other_bank:
            # If moved to other bank the next instruction has to be sequence type FRST again.
            return DebtCollectionBatch.SequenceTypes.FRST

        if self.instructions.filter(batch__status=DebtCollectionBatch.StatusChoices.NEW,
                                    batch__sequence_type=DebtCollectionBatch.SequenceTypes.FRST).exists():
            # If there is an ongoing FRST batch, the new type is not yet known.
            return None

        if self.instructions.filter(Q(reversal__isnull=True) | Q(reversal__pre_settlement=False),
                                    batch__status=DebtCollectionBatch.StatusChoices.PROCESSED).exists():
            # If there is a processed batch with this mandate, that does not have
            # a rejected presettlement, then this is a recurring instruction.
            return DebtCollectionBatch.SequenceTypes.RCUR

        # No processed instruction yet, so FRST.
        return DebtCollectionBatch.SequenceTypes.FRST

    def anonymize(self):
        """
        Remove personal information.

        Clears the person, iban, bic and account_holder_name fields.

        Clears the previous_iban and previous_bic fields of all related amendments.
        """
        self.person = None
        self.iban = ''
        self.bic = ''
        self.account_holder_name = ''
        self.save()

        for amendment in self.amendments.all():
            amendment.previous_iban = ''
            amendment.previous_bic = ''
            amendment.save()

    anonymize.alters_data = True

    def __str__(self):
        return self.authorization_reference()

    def get_absolute_url(self):
        return reverse('personal_tab:authorization_view', args=(), kwargs={'authorization_id': self.id, })

    class Meta:
        ordering = ['person', 'start_date']
        verbose_name = _l('mandate')
        verbose_name_plural = _l('mandates')


class Amendment(models.Model):
    """
    A change to an authorization.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """

    """The authorization that is being changed"""
    authorization = models.ForeignKey(Authorization, related_name='amendments', on_delete=models.PROTECT,
                                      verbose_name=_l('mandate'))

    """Date of the change"""
    date = models.DateField(verbose_name=_l('date'))

    """IBAN before change"""
    previous_iban = IBANField(verbose_name=_l('previous IBAN'), blank=True)

    """BIC before change"""
    previous_bic = BICField(verbose_name=_l('previous BIC'), blank=True)

    """This concerns a change to the bank of the person that gave the authorization."""
    other_bank = models.BooleanField(default=False, verbose_name=_l('other bank'))

    """Short description of the reason of the amendment."""
    reason = models.CharField(max_length=250, verbose_name=_l('remark'),
                              help_text=_l('Short description of the reason for the amendment'))

    def __str__(self):
        return _l('Amendment of %(authorization)s on %(date)s') % {'authorization': self.authorization,
                                                                    'date': self.date}

    class Meta:
        ordering = ['date']
        verbose_name = _l('amendment')
        verbose_name_plural = _l('amendments')


class DebtCollectionAssignment(models.Model):
    """
    An assignment for a debt collection.

    An assignment consists of one or more batches with instructions for debt collection.
    """

    """Prefix for file identification"""
    PREFIX = 'IA-MSG-'

    """Internal description of the assignment. Is not passed on to the bank or the cashed (the person paying)."""
    description = models.CharField(max_length=50, verbose_name=_l('description'))

    """Date and time this assignment was created."""
    created_on = models.DateTimeField(verbose_name=_l('created on'), auto_now_add=True)

    """Start date and time of the period this assignment is related to."""
    start = models.DateTimeField(verbose_name=_l('begin'), null=True, blank=True)

    """End date and time of the period this assignment is related to."""
    end = models.DateTimeField(verbose_name=_l('end'), null=True, blank=True)

    def file_identification(self):
        """Returns the file identification with prefix"""
        return '%s%08d' % (DebtCollectionAssignment.PREFIX, self.id)

    def number_of_transactions(self):
        return sum([batch.number_of_transactions() for batch in self.batches.all()])

    def control_sum(self):
        return sum([batch.control_sum() for batch in self.batches.all()])

    def reversed_sum(self):
        return sum([batch.reversed_sum() for batch in self.batches.all()])

    def __str__(self):
        return self.file_identification()

    def get_absolute_url(self):
        return reverse('personal_tab:debt_collection_view', args=(), kwargs={'id': self.id, })

    class Meta:
        ordering = ['-created_on']
        verbose_name = _l('Direct withdrawal-task')
        verbose_name_plural = _l('Direct withdrawal-tasks')


class DebtCollectionBatch(models.Model):
    """
    Batch for a debt collection.

    A batch consists of one or more instructions for debt collection, and is a part of a DebtCollectionAssignment.
    """

    class StatusChoices(models.TextChoices):
        """Possible sequence types for a debt collection batch."""
        NEW = 'N', _l("New")  # New batch
        PROCESSED = 'V', _l("Processed")  # The batch is processed by the bank and the debt collection is being executed.
        DECLINED = 'W', _l("Declined")  # The batch was declined by the bank.
        CANCELLED = 'A', _l("Cancelled")  # The batch was cancelled.

    class SequenceTypes(models.TextChoices):
        """Possible sequence types for a debt collection batch."""
        FRST = 'FRST', _l('First collection')  # First debt collection within a series on the same authorization.
        RCUR = 'RCUR', _l('Continuation of direct withdrawal')  # Continuation debt collection within the same authorization.
        FNAL = 'FNAL', _l('Last collection')  # Final debt collection within the same authorization.
        OOFF = 'OOFF', _l('One-time direct withdrawal')  # Singular debt collection without repetition.

    """Prefix for reference number"""
    PREFIX = 'IA-PMTINF-'

    """Assignment that this batch is a part of."""
    assignment = models.ForeignKey(DebtCollectionAssignment, related_name='batches', on_delete=models.PROTECT,
                                   verbose_name=_l('assignment'))

    """The date on which this debt collection batch should be executed."""
    execution_date = models.DateField(verbose_name=_l('date of execution'))

    """Sequence Type for this debt collection batch."""
    sequence_type = models.CharField(max_length=4, choices=SequenceTypes.choices, verbose_name=_l('sequence type'))

    """Status of this batch."""
    status = models.CharField(max_length=1, choices=StatusChoices.choices, verbose_name=_l('status'))

    def reference_number(self):
        """Returns the reference number with prefix."""
        return '%s%08d' % (DebtCollectionBatch.PREFIX, self.id)

    def number_of_transactions(self):
        return len(self.instructions.all())

    def control_sum(self):
        return sum([instruction.amount for instruction in self.instructions.all()])

    def reversed_sum(self):
        return sum([instruction.amount for instruction in self.instructions.filter(reversal__isnull=False)])

    def __str__(self):
        return self.reference_number()

    def get_absolute_url(self):
        return reverse('personal_tab:debt_collection_view', args=(), kwargs={'id': self.assignment.id, })

    class Meta:
        ordering = ['assignment', 'execution_date']
        verbose_name = _l('direct withdrawal-batch')
        verbose_name_plural = _l('direct withdrawal-batches')


class DebtCollectionInstruction(models.Model):
    """
    Instruction to collect some amount from a certain account.

    Part of a DebtCollectionBatch.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """

    """Prefix for debt collection reference."""
    PREFIX = 'IA-INSTR-'

    """Batch this instruction is a part of."""
    batch = models.ForeignKey(DebtCollectionBatch, related_name='instructions', on_delete=models.PROTECT,
                              verbose_name=_l('batch'))

    """Authorization that is used to collect this debt."""
    authorization = models.ForeignKey(Authorization, related_name='instructions', on_delete=models.PROTECT,
                                      verbose_name=_l('mandate'))

    """End-to-end-id. This will be passed on to the cashed (the person paying)."""
    end_to_end_id = models.CharField(max_length=35, verbose_name=_l('end-to-end-id'), validators=[SEPA_CHAR_VALIDATOR])

    """Description rule."""
    description = models.CharField(max_length=140, verbose_name=_l('description'), validators=[SEPA_CHAR_VALIDATOR])

    """Amount to be collected."""
    amount = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('amount'))

    """An amendment given with this instruction."""
    amendment = models.OneToOneField(Amendment, related_name='instruction', on_delete=models.PROTECT,
                                     verbose_name=_l('amendment'), null=True, blank=True)

    objects = DebtCollectionInstructionManager()

    def debt_collection_reference(self):
        """Returns the debt collection reference with prefix."""
        if self.id:
            return '%s%08d' % (DebtCollectionInstruction.PREFIX, self.id)

    def __str__(self):
        return self.debt_collection_reference() or 'New debt collection instruction'

    def get_absolute_url(self):
        return reverse('personal_tab:debt_collection_instruction_view', args=(), kwargs={'id': self.id, })

    class Meta:
        ordering = ['batch', 'authorization']
        verbose_name = _l('direct withdrawal-instruction')
        verbose_name_plural = _l('direct withdrawal-instructions')


class Reversal(models.Model):
    """
    Reversal of an already collected amount.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """


    class ReversalReasons(models.TextChoices):
        """Possible reasons for reversals"""
        AC01 = 'AC01', 'AC01 - IncorrectAccountNumber'
        AC04 = 'AC04', 'AC04 - ClosedAccountNumber'
        AC06 = 'AC06', 'AC06 - BlockedAccount'
        AC13 = 'AC13', 'AC13 - InvalidDebtorAccountType'
        AG01 = 'AG01', 'AG01 - TransactionForbidden'
        AG02 = 'AG02', 'AG02 - InvalidBankOperationCode'
        AGNT = 'AGNT', 'AGNT - IncorrectAgent'
        AM04 = 'AM04', 'AM04 - InsufficientFunds'
        AM05 = 'AM05', 'AM05 - Duplication'
        BE05 = 'BE05', 'BE05 - UnrecognisedInitiatingParty'
        CURR = 'CURR', 'CURR - IncorrectCurrency'
        CUST = 'CUST', 'CUST - RequestedByCustomer'
        DNOR = 'DNOR', 'DNOR - Debtor Bank is not registered under this BIC in the CSM'
        DUPL = 'DUPL', 'DUPL - DuplicatePayment'
        FF01 = 'FF01', 'FF01 - InvalidFileFormat'
        FF05 = 'FF05', 'FF05 - InvalidLocalInstrumentCode'
        MD01 = 'MD01', 'MD01 - NoMandate'
        MD02 = 'MD02', 'MD02 - MissingMandatoryInformationInMandate'
        MD06 = 'MD06', 'MD06 - RefundRequestByEndCustomer'
        MD07 = 'MD07', 'MD07 - EndCustomerDeceased'
        MS02 = 'MS02', 'MS02 - NotSpecifiedReasonCustomerGenerated'
        MS03 = 'MS03', 'MS03 - NotSpecifiedReasonAgentGenerated'
        RC01 = 'RC01', 'RC01 - BankIdentifierIncorrect'
        RR01 = 'RR01', 'RR01 - Missing Debtor Account or Identification'
        RR02 = 'RR02', 'RR02 - Missing Debtor Name or Address'
        RR03 = 'RR03', 'RR03 - Missing Creditor Name or Address'
        RR04 = 'RR04', 'RR04 - Regulatory Reason'
        SL01 = 'SL01', 'SL01 - Specific Service offered by Debtor Agent'

    """Debt collection instruction that was reversed."""
    instruction = models.OneToOneField(DebtCollectionInstruction, related_name='reversal', on_delete=models.PROTECT,
                                       verbose_name=_l('instruction'))

    """Date of reversal"""
    date = models.DateField(verbose_name=_l('Processing date'),
                            help_text=_l("Fill out processing date, not rent date. See Rabobank Internet Banking."))

    """Indicates if the reversal is a pre-settlement (REFUSAL) or post-settlement (RETURN or REFUND)."""
    pre_settlement = models.BooleanField(default=False, verbose_name=_l('pre-settlement'),
                                         help_text=_l("A debit reversal is pre-settlement when the withdrawal happens "
                                                     "before the crediting of the direct withdrawal has taken place."))

    """Reason for reversal"""
    reason = models.CharField(max_length=4, choices=ReversalReasons.choices, verbose_name=_l('reason'))

    def __str__(self):
        return _l('Debit reversal %s') % self.instruction.debt_collection_reference()

    class Meta:
        ordering = ['date']
        verbose_name = _l('debit reversal')
        verbose_name_plural = _l('reversal')


class DebtCollectionTransaction(Transaction):
    """
    Transaction for an executed debt collection.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    pass


class ReversalTransaction(Transaction):
    """
    Transaction for a debt transaction that was reversed.

    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """

    """Reversal that this transaction is related to."""
    reversal = models.OneToOneField(Reversal, related_name='transaction', on_delete=models.PROTECT,
                                    verbose_name=_l('debit reversal'))

    def get_absolute_url(self):
        return reverse('personal_tab:reversal_transaction_detail', args=[self.pk])


def get_sentinel_person() -> Person:
    return Person.objects.get(pk=settings.ANONIMIZATION_SENTINEL_PERSON_ID)


class PrintLogEntry(models.Model):
    """
    Log entry for a document printed by someone via the IA website.
    """

    actor = models.ForeignKey(Person, related_name='print_log', on_delete=models.SET(get_sentinel_person),
                              verbose_name=_l('Actor'))
    """The person that requested the printed document."""

    timestamp = models.DateTimeField(auto_now_add=True)
    """The timestamp on which the document print was requested."""

    source_ip = models.CharField(max_length=255, blank=True, null=True)
    """The IP address of the client that requested the document print."""

    source_useragent = models.CharField(max_length=255, blank=True, null=True)
    """The user agent of the client that requested the document print."""

    document_name = models.CharField(max_length=255, verbose_name=_l('Document name'))
    """The filename of the document that was printed."""

    job_id = models.CharField(max_length=255, verbose_name=_l('Printer Job ID'), blank=True, null=True)
    """The job ID that the printer assigned to the job. Useful to cross-reference with the logs on the printer."""

    page_count = models.IntegerField(verbose_name=_l('Page count'))
    """The number of pages in the printed document."""

    committee = models.ForeignKey(Committee, blank=True, null=True, default=None, related_name='print_log',
                                  on_delete=models.PROTECT)
    """The committee that the print was related to. Prints for committees are free, otherwise a transaction should be linked."""

    transaction = models.ForeignKey(CookieCornerTransaction, blank=True, null=True, default=None,
                                    related_name='print_log', on_delete=models.CASCADE)
    """A cookie corner transaction that pays for this print. Can be null if the print was for committee purposes."""

    class Meta:
        ordering = ['timestamp']
        verbose_name = _l('print log entry')
        verbose_name_plural = _l('print log entries')

    def __str__(self):
        return _l('%(actor)s printed %(pages)s page(s) %(for_str)s') % {
            'pages': self.page_count,
            'actor': self.actor,
            'for_str': (
                    (_l('for %(committee)s') % {'committee': self.committee})
                    if self.committee else
                    _l("for personal use")
                )
        }


def _complain_with_claudia(sender, **kwargs):
    instance = kwargs.get('instance')
    if instance.person:
        verify_instance(instance=instance.person)


def _complain_with_claudia_old(sender, **kwargs):
    """
    Verify old person if person has changed.

    Call from pre_save signal.
    """
    instance = kwargs.get('instance')
    try:
        instance_old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        # New instance, no previous value
        return

    if instance.person != instance_old.person:
        verify_instance(instance=instance_old.person)


post_save.connect(_complain_with_claudia, sender=Authorization)
pre_save.connect(_complain_with_claudia_old, sender=RFIDCard)
post_save.connect(_complain_with_claudia, sender=RFIDCard)
post_delete.connect(_complain_with_claudia, sender=RFIDCard)

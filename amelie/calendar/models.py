import uuid
from decimal import Decimal
from typing import List, Tuple, Optional

import pytz

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.db import models, transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import translation
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l

from amelie.files.models import Attachment
from amelie.calendar.managers import EventManager
from amelie.calendar.tasks import send_participation_callback
from amelie.members.models import Committee, Person
from amelie.personal_tab.models import ActivityTransaction
from amelie.personal_tab.transactions import get_transaction_payment_status
from amelie.tools.const import TaskPriority


class Participation(models.Model):
    person = models.ForeignKey(Person, verbose_name=_l('Person'), on_delete=models.PROTECT)
    event = models.ForeignKey('Event', verbose_name=_l('Activities'), on_delete=models.PROTECT)
    remark = models.TextField(blank=True, verbose_name=_l('Remarks'))
    waiting_list = models.BooleanField(verbose_name=_l("On waiting list"), default=False)

    added_on = models.DateTimeField(verbose_name=_l('Added on'), auto_now_add=True, null=True, blank=True)

    # '+' related name makes sure no backwards reference is created in Person
    added_by = models.ForeignKey(Person, blank=True, null=True, related_name="+", verbose_name=_l('Added by'), on_delete=models.PROTECT)

    class Meta:
        unique_together = [['person', 'event']]
        verbose_name = _l('Participation')
        verbose_name_plural = _l("Participations")

    def __str__(self):
        if hasattr(self, 'event'):
            return '(%s -> %s)' % (self.person, self.event)
        else:
            return '(%s -> %s)' % (self.person, _l('deleted activity'))

    def is_free(self) -> bool:
        """
        Returns if this participation is free and thus requires no payment.
        """
        return self.calculate_costs()[0] == 0

    def is_paid(self):
        """
        Participation is paid if it costs nothing, or if the newest ActivityTransaction that exists for it is paid.
        """
        if self.is_free():
            return True
        else:
            # The latest (by creation time) positive ActivityTransaction for this participation is the one that should be paid.
            # Other unpaid ones can exist if someone un/re-enrolled for the activity,
            # but they should all be compensated by a negative ActivityTransaction, thus they can be ignored.

            # Newest (by creation date) positive (or 0) price transaction
            current_transaction = self.activitytransaction_set.filter(price__gte=0).order_by('-added_on', '-pk').first()
            if current_transaction is not None:
                return current_transaction.is_paid()
            else:
                # Should not happen, but make a note of it in the logs if it does, and return that the participation is not paid.
                logging.getLogger(__name__).exception(f"Participation {self.pk} has no ActivityTransaction linked to it!")
                return False

    def payment_details(self):
        """
        Returns information on how this participation was paid, or how it might probably be paid in the future.
        Used mainly on the activity details page to quickly show the payment status and method of a Participation.

        If the participation is free, it returns ('free', None).
        Else, see the docstring of `personal_tab.transactions.get_transaction_payment_status`.
        """
        # If the participation is free, it returns None.
        if self.is_free():
            return 'free', None

        current_transaction = self.activitytransaction_set.filter(price__gte=0).order_by('-added_on', '-pk').first()
        return get_transaction_payment_status(_transaction=current_transaction, mandate_type='activities')

    def calculate_costs(self) -> Tuple[Decimal, bool]:
        from amelie.activities.models import Activity

        # For now only Activities!
        try:
            activity = Activity.objects.get(event_ptr=self.event)
        except:
            raise NotImplementedError("Non-activities are not yet supported!")

        # List of extra costs per enrollment option
        prices_extra: List[Decimal] = [
            enrollment_option_answer.get_price_extra() for enrollment_option_answer in self.enrollmentoptionanswer_set.all()
        ]
        # Calculate and return total costs, and if there were any additional costs due to enrollment options.
        total_costs = activity.price + sum(prices_extra)
        return total_costs, len(prices_extra) > 0

    @property
    def unpaid_transactions(self):
        return [t for t in self.activitytransaction_set.all() if not t.is_paid()]

    @property
    def unsettled_transactions(self):
        return [t for t in self.activitytransaction_set.filter(settlement=None)]

    @property
    def to_be_paid_costs(self):
        """
        Calculate the open costs for this participation, considering all transactions that relate to it.
        """
        return sum(t.price for t in self.unpaid_transactions) or Decimal("0.00")

    @transaction.atomic
    def mark_as_paid(self, payment_method, actor: Optional[Person] = None):
        """
        Mark any unpaid ActivityTransaction(s) for this participation as paid, with the given payment method.
        """
        # Avoid circular import
        from amelie.personal_tab.models import ManualPaymentSettlement

        # Get the ActivityTransaction(s) for this Participation that still need to be paid
        ats = self.unsettled_transactions
        if not ats:
            return None

        # Override language to get the description strings in the person's preferred language
        with translation.override(self.person.preferred_language):
            # Create a ManualPayment settlement with the given payment method to mark the activity transactions as paid.
            description = _("Payment for enrollment to {event} on {date}").format(
                event=self.event.summary_en, date=self.event.begin.date()
            )
            settlement = ManualPaymentSettlement.create_for_transactions(
                transactions=ats,
                payment_method=payment_method,
                person=self.person,
                settlement_description=description,
                payment_description=description,
                created_by=actor
            )
        return settlement


@receiver(post_save, sender=Participation)
def post_save_callback(sender, instance, **kwargs):
    callback_args = [instance.event.id, instance.person.id, 'signup']
    send_participation_callback.s(*callback_args).set(priority=TaskPriority.URGENT).delay()


@receiver(post_delete, sender=Participation)
def post_delete_callback(sender, instance, **kwargs):
    callback_args = [instance.event.id, instance.person.id, 'signout']
    send_participation_callback.s(*callback_args).set(priority=TaskPriority.URGENT).delay()


def _generate_callback_secret_key():
    return str(uuid.uuid4())


class Event(models.Model):
    """
    Activity/Event that can be transformed into <x>Calendar format.
    """
    begin = models.DateTimeField(verbose_name=_l('Starts'))
    end = models.DateTimeField(verbose_name=_l('Ends'))
    entire_day = models.BooleanField(default=False, verbose_name=_l('All day'))

    summary_nl = models.CharField(max_length=250, verbose_name=_l('Summary'))
    summary_en = models.CharField(max_length=250, blank=True, null=True, verbose_name=_l("Summary (en)"))

    promo_nl = models.TextField(blank=True, verbose_name=_l('Short promotional message'),
        help_text=_l('This text can be used by the board for promotion, for example on our socials or in our weekmail. '
                    'Let it be a teaser, so people would want to read your full activity description.'))
    promo_en = models.TextField(blank=True, verbose_name=_l('Short promotional message'),
        help_text=_l(
            'This text can be used by the board for promotion, for example on our socials or in our weekmail. '
            'Let it be a teaser, so people would want to read your full activity description.'))

    description_nl = models.TextField(blank=True, verbose_name=_l('Description'))
    description_en = models.TextField(blank=True, null=True, verbose_name=_l("Description (en)"))

    organizer = models.ForeignKey(Committee, verbose_name=_l('Organizer'), on_delete=models.PROTECT)
    location = models.CharField(max_length=200, blank=True, verbose_name=_l('Location'))
    participants = models.ManyToManyField(Person, through=Participation, blank=True, through_fields=('event', 'person'),
                                          verbose_name=_l('Participants'))
    public = models.BooleanField(default=True, verbose_name=_l('Public'))
    attachments = models.ManyToManyField(Attachment, blank=True, verbose_name=_l('Attachments'))
    dutch_activity = models.BooleanField(default=False, verbose_name=_l('Dutch-only'))

    callback_url = models.CharField(blank=True, verbose_name=_l('Callback URL'), max_length=255, validators=[
        RegexValidator(regex='^https://.*', message=_l('URL has to start with https://')), URLValidator()])
    callback_secret_key = models.CharField(blank=True, default=_generate_callback_secret_key, max_length=255)

    cancelled = models.BooleanField(default=False, verbose_name=_l('Cancel event'),
                                    help_text=_l('Whether this event is cancelled, only cancel when needed. Participants will receive an email notification!'))

    update_count = models.PositiveIntegerField(default=0)

    objects = EventManager()

    class Meta:
        ordering = ['begin']
        verbose_name = _l('Activities')
        verbose_name_plural = _l('Activities')

    def as_leaf_class(self):
        """
        Converts this Event instance into its Subclass instance.
        (e.g. from Event to Activity, EducationEvent and CompanyEvent)
        :rtype: Activity | EducationEvent | CompanyEvent
        """
        logger = logging.getLogger(__name__)
        if hasattr(self, 'activity'):
            return self.activity
        elif hasattr(self, 'educationevent'):
            return self.educationevent
        elif hasattr(self, 'companyevent'):
            return self.companyevent
        else:
            # Unknown event type
            logger.warning("Unknown event type for Event {}, {}. Did you add a new subclass to Event "
                           "without fixing the get_subclass_instance method?!".format(self.pk, self.summary_nl))
            return self

    @property
    def summary(self):
        language = get_language()

        summ = None
        if language == "en" and self.summary_en:
            summ = self.summary_en
        else:
            summ = self.summary_nl

        if self.cancelled:
            summ = f"[CANCELLED] {summ}"
        return summ

    @property
    def description(self):
        language = get_language()

        if language == "en" and self.description_en:
            return self.description_en
        else:
            return self.description_nl

    @property
    def promo(self):
        language = get_language()

        if language == "en" and self.promo_en:
            return self.promo_en
        else:
            return self.promo_nl

    def __str__(self):
        return str(self.summary)

    def clean(self):
        super(Event, self).clean()

        if self.begin is not None and self.end is not None:
            if self.begin >= self.end:
                raise ValidationError(
                    {"begin": [_l('Start may not be after of simultaneous to end.')]})

    def save(self, *args, **kwargs):
        self.update_count += 1
        super(Event, self).save(*args, **kwargs)

    def description_short(self):
        tz = pytz.timezone(settings.TIME_ZONE)

        char_limit = 150
        location_prefix = " @" if self.location != "" else ""
        activity_prefix = (self.as_leaf_class().activity_label.name_en + " - ") if self.as_leaf_class().activity_label else ""
        total_string = f"{activity_prefix}{self.begin.astimezone(tz).strftime('%d/%m/%Y, %H:%M')}{location_prefix}{self.location} {self.promo_en}"

        if len(total_string) > char_limit:
            total_string = total_string[:char_limit] + '...'
        return total_string

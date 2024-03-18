import itertools
import uuid

import logging
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from amelie.files.models import Attachment
from amelie.calendar.managers import EventManager
from amelie.calendar.tasks import send_participation_callback
from amelie.members.models import Committee, Person
from amelie.personal_tab.models import ActivityTransaction


class Participation(models.Model):
    class PaymentMethodChoices(models.TextChoices):
        NONE = '-', _('No payment')
        CASH = 'C', _('Cash at the board/committee')
        AUTHORIZATION = 'M', _('Mandate')

    person = models.ForeignKey(Person, verbose_name=_('Person'), on_delete=models.PROTECT)
    event = models.ForeignKey('Event', verbose_name=_('Activities'), on_delete=models.PROTECT)
    remark = models.TextField(blank=True, verbose_name=_('Remarks'))

    payment_method = models.CharField(max_length=1, choices=PaymentMethodChoices.choices, verbose_name=_('Method of payment'))
    cash_payment_made = models.BooleanField(verbose_name=_("Cash payment made"), default=False)
    waiting_list = models.BooleanField(verbose_name=_("On waiting list"), default=False)

    added_on = models.DateTimeField(verbose_name=_('Added on'), auto_now_add=True, null=True, blank=True)

    # '+' related name makes sure no backwards reference is created in Person
    added_by = models.ForeignKey(Person, blank=True, null=True, related_name="+", verbose_name=_('Added by'), on_delete=models.PROTECT)

    class Meta:
        unique_together = [['person', 'event']]
        verbose_name = _('Participation')
        verbose_name_plural = _("Participations")

    def __str__(self):
        if hasattr(self, 'event'):
            return '(%s -> %s)' % (self.person, self.event)
        else:
            return '(%s -> %s)' % (self.person, _('deleted activity'))

    def has_paid(self):
        return not (self.payment_method == Participation.PaymentMethodChoices.CASH and self.cash_payment_made == False)

    def calculate_costs(self):
        from amelie.activities.models import Activity

        # For now only Activities!
        try:
            activity = Activity.objects.get(event_ptr=self.event)
        except:
            raise NotImplementedError("Non-activities are not yet supported!")

        prices_extra = (enrollment_option_answer.get_price_extra() for enrollment_option_answer in
                        self.enrollmentoptionanswer_set.all())

        with_enrollment_option, prices_extra = _has_next(prices_extra)

        return activity.price + sum(prices_extra), with_enrollment_option


@receiver(post_save, sender=Participation)
def post_save_callback(sender, instance, **kwargs):
    send_participation_callback.delay(instance.event.id, instance.person.id, 'signup')


@receiver(post_delete, sender=Participation)
def post_delete_callback(sender, instance, **kwargs):
    send_participation_callback(instance.event.id, instance.person.id, 'signout')


def _generate_callback_secret_key():
    return str(uuid.uuid4())


class Event(models.Model):
    """
    Activity/Event that can be transformed into <x>Calendar format.
    """
    begin = models.DateTimeField(verbose_name=_('Starts'))
    end = models.DateTimeField(verbose_name=_('Ends'))
    entire_day = models.BooleanField(default=False, verbose_name=_('All dag'))

    summary_nl = models.CharField(max_length=250, verbose_name=_('Summary'))
    summary_en = models.CharField(max_length=250, blank=True, null=True, verbose_name=_("Summary (en)"))

    promo_nl = models.TextField(blank=True, verbose_name=_('Short promotional message'),
        help_text=_('This text can be used by the board for promotion, for example on our socials or in our weekmail. '
                    'Let it be a teaser, so people would want to read your full activity description.'))
    promo_en = models.TextField(blank=True, verbose_name=_('Short promotional message'),
        help_text=_(
            'This text can be used by the board for promotion, for example on our socials or in our weekmail. '
            'Let it be a teaser, so people would want to read your full activity description.'))

    description_nl = models.TextField(blank=True, verbose_name=_('Description'))
    description_en = models.TextField(blank=True, null=True, verbose_name=_("Description (en)"))

    organizer = models.ForeignKey(Committee, verbose_name=_('Organizer'), on_delete=models.PROTECT)
    location = models.CharField(max_length=200, blank=True, verbose_name=_('Location'))
    participants = models.ManyToManyField(Person, through=Participation, blank=True, through_fields=('event', 'person'),
                                          verbose_name=_('Participants'))
    public = models.BooleanField(default=True, verbose_name=_('Public'))
    attachments = models.ManyToManyField(Attachment, blank=True, verbose_name=_('Attachments'))
    dutch_activity = models.BooleanField(default=False, verbose_name=_('Dutch-only'))

    callback_url = models.CharField(blank=True, verbose_name=_('Callback URL'), max_length=255, validators=[
        RegexValidator(regex='^https://.*', message=_('URL has to start with https://')), URLValidator()])
    callback_secret_key = models.CharField(blank=True, default=_generate_callback_secret_key, max_length=255)

    cancelled = models.BooleanField(default=False, verbose_name=_('Cancel event'),
                                    help_text=_('Whether this event is cancelled, only cancel when needed. Participants will receive an email notification!'))

    update_count = models.PositiveIntegerField(default=0)

    objects = EventManager()

    class Meta:
        ordering = ['begin']
        verbose_name = _('Activities')
        verbose_name_plural = _('Activities')

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
                    {"begin": [_('Start may not be after of simultaneous to end.')]})

    def save(self, *args, **kwargs):
        self.update_count += 1
        super(Event, self).save(*args, **kwargs)

    def description_short(self):
        char_limit = 150
        total_string = f"{self.begin.strftime('%d/%m/%Y, %H:%M')} @{self.location} {self.promo_en}"

        if len(total_string) > char_limit:
            total_string = total_string[:char_limit] + '...'
        return total_string

def _has_next(iterable):
    try:
        first = next(iterable)
    except StopIteration:
        return False, []
    return True, itertools.chain([first], iterable)

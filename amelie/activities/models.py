from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List, Type

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Sum, QuerySet
from django.dispatch import receiver
from django.urls import reverse
from django.db import models, transaction
from django.db.models.signals import post_save, pre_save, pre_delete
from django.utils import timezone, translation
from django.utils.timezone import make_aware
from django.utils.translation import gettext as _
from django.utils.translation import get_language, gettext_lazy as _l
from oauth2_provider.models import Application

from amelie.activities.mail import activity_send_enrollmentmail, activity_send_cancellationmail
from amelie.tools.locale import setlocale
from amelie.files.models import Attachment
from amelie.calendar.managers import EventManager
from amelie.calendar.models import Event, Participation
from amelie.members.models import Person
from amelie.tools.discord import send_discord, send_discord_presave
from amelie.tools.managers import SubclassManager


class ActivityLabel(models.Model):
    name_en = models.CharField(verbose_name=_l("Name (en)"), max_length=32)
    name_nl = models.CharField(verbose_name=_l("Name"), max_length=32)
    color = models.CharField(verbose_name=_l("Hexcolor without #"), max_length=6)
    icon = models.CharField(verbose_name=_l("Icon from known icons"), max_length=32)
    explanation_en = models.TextField(verbose_name=_l("Explanation on icon (en)"))
    explanation_nl = models.TextField(verbose_name=_l("Explanation on icon"))
    active = models.BooleanField(verbose_name=_l("Active?"), default=True)

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    @property
    def explanation(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.explanation_en
        else:
            return self.explanation_nl

    def __str__(self):
        if self.active:
            return self.name
        return f"{self.name} (inactive)"


class Activity(Event):
    enrollment = models.BooleanField(default=False, verbose_name=_l('enrollment'))
    enrollment_begin = models.DateTimeField(blank=True, null=True, verbose_name=_l('enrollment start'), help_text=_l('If you want to add options, make sure your activity isn\'t open for enrollment right away'))
    enrollment_end = models.DateTimeField(blank=True, null=True, verbose_name=_l('enrollment end'))
    enrollment_private = models.BooleanField(default=False, verbose_name=_l('Hide participants'))
    maximum = models.PositiveIntegerField(blank=True, null=True)
    waiting_list_locked = models.BooleanField(default=False, verbose_name=_l('Lock waiting list'))

    photos = models.ManyToManyField(Attachment, blank=True, related_name='foto_set')
    components = models.ManyToManyField('self', blank=True)

    price = models.DecimalField(default="0.00", max_digits=8, decimal_places=2, verbose_name=_l('price'), help_text=_l("Enrolled participants will be emailed when you change the price."))
    can_unenroll = models.BooleanField(default=True, verbose_name=_l('can unenroll'))

    image_icon = models.ImageField(upload_to='activities/icon/', max_length=255, null=True, blank=True, verbose_name=_l('icon'), help_text=_l('Image of 175 by 275 pixels.'))

    facebook_event_id = models.CharField(max_length=150, blank=True, help_text=_l("Facebook event id, numerical value in the facebook event url."))

    activity_label = models.ForeignKey(ActivityLabel, on_delete=models.PROTECT)

    oauth_application = models.ForeignKey(Application, blank=True, null=True, on_delete=models.SET_NULL)

    objects = EventManager()  # Is only inherited when if the Event would be abstract...

    class Meta:
        ordering = ['begin']
        verbose_name = _l('Activities')
        verbose_name_plural = _l('Activities')

    def __str__(self):
        return self.summary

    def clean(self):
        super(Activity, self).clean()

        if self.enrollment:
            if self.enrollment_begin is None:
                raise ValidationError(_l('There is no enrollment start date entered.'))

            if self.enrollment_end is None:
                raise ValidationError(_l('There is no enrollment end date entered.'))

    ##
    # Properties and simple getter functions
    ##

    @property
    def activity_type(self) -> str:
        return "regular"

    @property
    def confirmed_participants(self) -> QuerySet['Person']:
        return self.participants.filter(participation__waiting_list=False)

    @property
    def confirmed_participations(self) -> QuerySet['Participation']:
        return self.participation_set.filter(waiting_list=False)

    @property
    def waiting_participants(self) -> QuerySet['Person']:
        return self.participants.filter(participation__waiting_list=True)

    @property
    def waiting_participations(self) -> QuerySet['Participation']:
        return self.participation_set.filter(waiting_list=True)

    @property
    def enrollment_open(self) -> bool:
        """Shows whether the enrollment is open at this time"""
        return self.enrollment_begin < timezone.now() < self.enrollment_end

    @property
    def enrollment_closed(self) -> bool:
        """
        If True, then the enrollment deadline is over, thus you are too late to enroll.
        """
        return timezone.now() > self.enrollment_end

    @property
    def places_available(self) -> Optional[int]:
        """
        Calculates the number of available places.
        If there is no maximum, then the result of this function is None.
        """
        return max(0, self.maximum - self.participants.filter(participation__waiting_list=False).count()) if self.maximum else None

    @property
    def enrollment_full(self) -> bool:
        """
        True if there are no more places available to enroll and if there is a maximum.
        """
        places_available = self.places_available
        return places_available is not None and places_available == 0

    @property
    def has_waiting_participants(self) -> bool:
        """
        True if there is a waiting list that is not empty.
        """
        return self.waiting_participants.count() > 0

    @property
    def enrollment_almost_full(self) -> bool:
        """
        True if there are less than ten places available and if there is a maximum.
        """
        places_available = self.places_available
        return places_available is not None and places_available <= 10

    @property
    def has_enrollmentoptions(self) -> bool:
        return self.enrollmentoption_set.exists()

    @property
    def has_costs(self) -> bool:
        """
        An activity has costs if there are enrollment costs, or if there are
        enrollment options, optional or not, that have costs. In this case the
        function will return True.

        It does not matter if enrollment costs or enrollment options result in
        a discount.
        """
        # Trivial check
        if self.price != 0:
            return True

        # Check every option
        return any([enrollmentoption.has_extra_costs() for enrollmentoption
                    in self.enrollmentoption_set.all()])

    @property
    def latest_event_registration_message(self) -> Optional['EventDeskRegistrationMessage']:
        return self.eventdeskregistrationmessage_set.all().order_by('-message_date').first()

    def get_absolute_url(self) -> str:
        return reverse('activities:activity', args=[self.id])

    def get_photo_url_random(self) -> str:
        return reverse('activities:random_photo', args=[self.id])

    def get_photo_url(self) -> str:
        return reverse('activities:gallery', args=[self.id])

    def get_calendar_url(self) -> str:
        return reverse('activities:ics', args=[self.id])

    def random_photo(self, only_public=True) -> Optional['Attachment']:
        photos: QuerySet['Attachment'] = self.photos.filter_public(only_public)

        # Select a random photo
        photo = photos.order_by('?')[:1]

        # Done
        return photo[0] if len(photo) > 0 else None

    def random_public_photo(self) -> Optional['Attachment']:
        return self.random_photo(only_public=True)

    def can_edit(self, person) -> bool:
        return person.is_board() or (self.organizer in person.current_committees()) or person.user.is_superuser

    ##
    # Enrollment helper functions
    ##
    def check_enrollment_allowed(self, person: Person, indirect: bool = False,
                                 ignore_start_enrollment: bool = False,
                                 authentication_application: Optional[Application] = None) -> Tuple[bool, Optional[str]]:
        """Checks whether a person can enroll for this activity

        :param person: The person who wants to enroll for an activity, standard is request.person
        :param indirect: Whether the enrollment is done by the person him-/herself, or done for him/her
        :param ignore_start_enrollment: Ignore the enrollment period of the activity
        :param authentication_application: The oauth application being used to process this enrollment
        :returns: Whether the person can enroll for the given activity
        """
        if not self.enrollment:
            return False, _l('Enrollment for {activity} is not possible.').format(activity=self)

        if not person.is_member():
            return False, _l(
                'Enrollment for {activity} is not possible. You do not have an active membership at Inter-Actief'
            ).format(activity=self)

        if self.oauth_application and (authentication_application is None or self.oauth_application != authentication_application):
            return False, _l(
                'Enrollment for {activity} is only possible on the website of this activity.'
            ).format(activity=self)

        if not self.enrollment_open:
            if not ignore_start_enrollment:
                return False, _l(
                    "The enrollment period for {activity} hasn't started yet or has already passed."
                ).format(activity=self)

        if person in self.participants.all():
            if indirect:
                return False, _l('{person} is already enrolled for {activity}.').format(
                    person=person,
                    activity=self
                )
            else:
                return False, _l('You are already enrolled for {activity}.').format(activity=self)

        return True, None

    def check_unenrollment_allowed(self, person: Person, indirect: bool = False, ignore_can_unenroll: bool = False,
                                   ignore_unenrollment_period: bool = False,
                                   authentication_application: Optional[Application] = None) -> Tuple[bool, Optional[str]]:
        """Checks whether a person can unenroll for an activity

        :param person: The person who wants to unenroll for an activity, standard is request.person
        :param indirect: Whether the unenrollment is done by the person him-/herself or for him/her
        :param ignore_can_unenroll: Ignore the unenrollment prohibition of the activity
        :param ignore_unenrollment_period: Ignore the unenrollment period of the activity
        :param authentication_application: The oauth application being used to process this unenrollment
        :returns: Whether the person can unenroll for the given activity

        :side_effect: Puts an elaborate description of the error in django messages
        """
        if not self.enrollment:
            return False, _l('Unenrollment for {activity} is not possible.').format(activity=self)

        if self.oauth_application and (authentication_application is None or self.oauth_application != authentication_application):
            return False, _l(
                'Unenrollment for {activity} is only possible on the website of this activity.'
            ).format(activity=self)

        try:
            # The select_for_update makes sure to acquire a write lock
            Participation.objects.select_for_update().get(person=person, event=self)
        except Participation.DoesNotExist:
            if indirect:
                return False, _l('{person} is not enrolled for {activity}.').format(
                    person=person,
                    activity=self
                )
            else:
                return False, _l('You are not enrolled for {activity}.').format(activity=self)

        if not self.can_unenroll and not ignore_can_unenroll:
            return False, _l('Unenrollment for {activity} is not possible.').format(activity=self)

        if not self.enrollment_open and not ignore_unenrollment_period:
            return False, _l('The unenrollment term for {activity} has already passed.').format(activity=self)

        return True, None

    @transaction.atomic
    def update_waiting_list(self) -> List[Participation]:
        """
        Checks if any participants on the waiting list for this activity can be enrolled into the activity.
        If there is room, the participants will be definitively enrolled.

        The list of newly enrolled participants is returned.

        :return: List of newly enrolled participants
        :rtype: List[Participation]
        """
        new_participants: List[Participation] = []
        while not self.enrollment_full and self.has_waiting_participants and not self.waiting_list_locked:
            new_participation = Participation.objects.get(
                person=self.waiting_participants.order_by('participation__added_on').first(),
                event=self
            )
            activity_send_enrollmentmail(new_participation, from_waiting_list=True)
            new_participation.waiting_list = False
            new_participation.save()
            from amelie.personal_tab import transactions
            transactions.add_participation(new_participation, added_by=new_participation.added_by)
            new_participants.append(new_participation)
        return new_participants

    @transaction.atomic
    def unenroll_all_participants(self, actor: Optional[Person] = None):
        """
        Neatly unenroll all participants from this activity, undoing any transactions that
        may have been added to the personal tabs of the participants.
        :param actor: A person that is registered as the 'added by' actor for the cancellation transaction.
        :type actor: Person
        """
        # Undo transactions and remove participations
        from amelie.personal_tab import transactions
        for participation in self.participation_set.all():
            # If necessary, compensate the person for the enrollment costs.
            with translation.override(participation.person.preferred_language):
                transactions.remove_participation(participation, added_by=actor, reason=_("Activity was cancelled"))
            # Remove the participation
            participation.delete()

    @transaction.atomic
    def cancel_activity(self, actor: Optional[Person] = None):
        """
        Cancel this activity.
        Events may only be canceled if they have not yet started.
        This will also remove all enrollments (and closes the option to enroll) and undoes the corresponding transactions.
        :param actor: A person that is registered as the 'added by' actor for the cancellation transaction.
        :type actor: Person
        """
        # Can only cancel if the activity hasn't started yet.
        if self.begin < timezone.now():
            raise ValueError(_("Activity has already started, it cannot be canceled any more."))

        # Send cancellation e-mails
        # First to regular participants (filtered by waiting_list=False)
        activity_send_cancellationmail(self.participation_set.filter(waiting_list=False), self)
        # Then to waiting list participants, if present
        if self.waiting_participations.exists():
            activity_send_cancellationmail(self.waiting_participations.all(), self, from_waiting_list=True)

        # Undo transactions and remove participations
        self.unenroll_all_participants(actor=actor)

        # Mark the activity as canceled and close enrollments.
        self.cancelled = True
        self.enrollment = False
        self.save()

    def uncancel_activity(self):
        """
        Uncancel an activity.
        The cancellation status will be removed, but enrollments will not be re-opened
        (because we can't know if it was open before).
        """
        self.cancelled = False
        self.save()

    def enroll_person(self, person: Person):
        # TODO Implement
        pass

    def unenroll_person(self, person: Person):
        # TODO Implement
        pass

    def edit_enrollment(self, participation: Participation):
        # TODO Implement
        pass



class Enrollmentoption(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    title = models.CharField(max_length=250, verbose_name=_l('Title'))
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)

    objects = SubclassManager()

    class Meta:
        verbose_name = _l('Enrollment option')
        verbose_name_plural = _l('Enrollment options')

    def __str__(self):
        return '%s (%s)' % (self.title, self.content_type)

    def save(self, *args, **kwargs):
        if not self.content_type:
            self.content_type = ContentType.objects.get_for_model(self.__class__)

        super(Enrollmentoption, self).save(*args, **kwargs)

    def has_extra_costs(self):
        return False

    def as_leaf_class(self, enforce_content_type=None):
        if enforce_content_type is not None:
            content_type = enforce_content_type
        else:
            content_type = self.content_type

        model = content_type.model_class()

        if model == Enrollmentoption:
            return self

        if self.id is None:
            new_model = model()
            new_model.activity = self.activity
            new_model.title = self.title
            new_model.content_type = self.content_type
        else:
            new_model = model.objects.get(id=self.id)

        return new_model


class EnrollmentoptionQuestion(Enrollmentoption):
    """
    Standard option where a question can be filled in, mandatory or not.
    """

    required = models.BooleanField(default=True, verbose_name=_l('Required'))
    objects = SubclassManager()


class EnrollmentoptionCheckbox(Enrollmentoption):
    """
    Deelname-option in the form of a checkbox. It is possible to increase the
    total costs of enrollment. For example by choosing for transportation as
    an option for a LAN-party.

    price_extra     -- Defines the extra costs (or discount)
    """

    price_extra = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price extra'), help_text=_l("Enrolled participants will be emailed when you change the price."), default=0)
    maximum = models.IntegerField(verbose_name=_l("Maximum limit of selections"), help_text=_l("Set as 0 for unlimited"), default=0)
    objects = SubclassManager()

    def has_extra_costs(self):
        return bool(self.price_extra)

    def has_limit(self):
        return self.maximum != 0

    def count_spots_left(self):
        if self.maximum == 0:
            return None
        return self.maximum - self.enrollmentoptionanswer_set.filter(enrollmentoptioncheckboxanswer__answer=True).count()

    def spots_left(self):
        return self.count_spots_left() is None or self.count_spots_left() > 0

class EnrollmentoptionNumeric(Enrollmentoption):
    """
    Deelname-option in the form of a numeric option. It is possible to increase the
    total costs of enrollment by the numeric option. For example by buying X socks.

    price_extra     -- Defines the extra costs (or discount)
    """

    price_extra = models.DecimalField(max_digits=8, decimal_places=2, help_text=_l("Enrolled participants will be emailed when you change the price."), verbose_name=_l('Price extra'), default=0)
    maximum = models.IntegerField(verbose_name=_l("Maximum limit of selections"), help_text=_l("Set as 0 for unlimited"), default=0)
    maximum_per_person = models.IntegerField(verbose_name=_l("Maximum per person"), help_text=_l("Set as 0 for unlimited"), default=0)
    objects = SubclassManager()

    def has_extra_costs(self):
        return bool(self.price_extra)

    def has_limit(self):
        return self.maximum != 0

    def count_spots_left(self):
        if self.maximum == 0:
            return None
        count = self.enrollmentoptionanswer_set.aggregate(Sum('enrollmentoptionnumericanswer__answer'))
        if count is None or count.get('enrollmentoptionnumericanswer__answer__sum') is None:
            return self.maximum
        return self.maximum - count.get('enrollmentoptionnumericanswer__answer__sum')

    def spots_left(self):
        return self.count_spots_left() is None or self.count_spots_left() > 0

class EnrollmentoptionSelectbox(Enrollmentoption):
    """
    Enrollment-option which is a selectbox. Every choice has a specific price.
    """

    objects = SubclassManager()

    def has_extra_costs(self):
        return any([selectboxoption.price_extra for selectboxoption in self.selectboxoption_set.all()])


class SelectboxOption(models.Model):
    """
    A single option of a selectbox has both a description (text) and a price.
    """

    text = models.CharField(max_length=250)
    price_extra = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price extra'), default=0)

    selection_option = models.ForeignKey(EnrollmentoptionSelectbox, on_delete=models.CASCADE)


class EnrollmentoptionAnswer(models.Model):
    enrollment = models.ForeignKey(Participation, on_delete=models.CASCADE)
    enrollmentoption = models.ForeignKey(Enrollmentoption, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)

    objects = SubclassManager()

    class Meta:
        verbose_name = _l('Answer to enrollment option')
        verbose_name_plural = _l('Anwers to enrollment option')

    @property
    def display_answer(self):
        return self.answer

    def is_empty(self):
        raise NotImplementedError('Cannot be called on base class')

    def __str__(self):
        return '%s' % self.content_type

    def save(self, *args, **kwargs):
        if not self.content_type:
            self.content_type = ContentType.objects.get_for_model(self.__class__)

        super(EnrollmentoptionAnswer, self).save(*args, **kwargs)

    def as_leaf_class(self, enforce_content_type=None):
        if enforce_content_type is not None:
            content_type = enforce_content_type
        else:
            content_type = self.content_type

        model = content_type.model_class()

        if model == EnrollmentoptionQuestion:
            return self

        if self.id is None:
            new_model = model()
            new_model.enrollmentoption = self.enrollmentoption
            new_model.enrollment = self.enrollment
            new_model.content_type = self.content_type
        else:
            new_model = model.objects.get(id=self.id)

        return new_model

    def get_price_extra(self) -> Decimal:
        """
        Calculate extra costs based on data
        """
        return Decimal("0")


class EnrollmentoptionQuestionAnswer(EnrollmentoptionAnswer):
    answer = models.CharField(max_length=250, blank=True, verbose_name=_l('Respons'))
    objects = SubclassManager()

    @property
    def display_answer(self):
        return self.answer or "-"

    def is_empty(self):
        return EnrollmentoptionQuestionAnswer.objects.filter(id=self.id).filter(answer__exact='').exists()

    def clean(self):
        if self.enrollmentoption.enrollmentoptionquestion.required and len(self.answer) == 0:
            raise ValidationError(_l('A response is required'))


class EnrollmentoptionCheckboxAnswer(EnrollmentoptionAnswer):
    answer = models.BooleanField(default=False, verbose_name=_l('Respons'))
    objects = SubclassManager()

    @property
    def display_answer(self):
        return _l("Yes") if self.answer else _l("No")

    def is_empty(self):
        return EnrollmentoptionCheckboxAnswer.objects.filter(id=self.id).filter(answer=False).exists()

    def get_price_extra(self) -> Decimal:
        if self.answer:
            return self.enrollmentoption.enrollmentoptioncheckbox.price_extra
        else:
            return super(EnrollmentoptionCheckboxAnswer, self).get_price_extra()


class EnrollmentoptionNumericAnswer(EnrollmentoptionAnswer):
    answer = models.IntegerField(default=0, verbose_name=_l('Respons'), validators=[MinValueValidator(0)])
    objects = SubclassManager()

    @property
    def display_answer(self):
        return self.answer

    def is_empty(self):
        return EnrollmentoptionNumericAnswer.objects.filter(id=self.id).filter(answer=0).exists()

    def get_price_extra(self) -> Decimal:
        return self.enrollmentoption.enrollmentoptionnumeric.price_extra * self.answer


class EnrollmentoptionSelectboxAnswer(EnrollmentoptionAnswer):
    answer = models.ForeignKey(SelectboxOption, verbose_name=_l('Respons'), on_delete=models.CASCADE)
    objects = SubclassManager()

    @property
    def display_answer(self):
        return self.answer or _l("(none)")

    def is_empty(self):
        return EnrollmentoptionSelectboxAnswer.objects.filter(id=self.id).filter(answer__isnull=True).exists()

    def get_price_extra(self) -> Decimal:
        return self.answer.price_extra


### Food options
class Restaurant(models.Model):
    name = models.CharField(max_length=64)
    available = models.BooleanField(default=True)

    def __str__(self):
        return '%s' % self.name


class Dish(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT, verbose_name=_l('Restaurant'))
    name = models.CharField(max_length=64, verbose_name=_l('Name'))
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price'))
    available = models.BooleanField(default=True, verbose_name=_l('Available'))
    allergens = models.TextField(verbose_name=_l('Allergens'), default=_l('No information available'), blank=True)

    def __str__(self):
        if self.available:
            return '%s (%s)' % (self.name, self.restaurant)
        else:
            return '%s (%s) (unavailable)' % (self.name, self.restaurant)


class EnrollmentoptionFood(Enrollmentoption):
    required = models.BooleanField(default=True, verbose_name=_l('Required'))
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT, verbose_name=_l('Restaurant'))

    def has_extra_costs(self):
        return any([bool(dishprice.price) for dishprice in self.dishprice_set.all()])


class DishPriceManager(models.Manager):
    def get_queryset(self):
        return super(DishPriceManager, self).get_queryset().filter(dish__available=True)


class DishPrice(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    question = models.ForeignKey(EnrollmentoptionFood, verbose_name=_l('Enrollment optionquestion'), on_delete=models.CASCADE)

    # Hide unavailable options by default
    objects = DishPriceManager()
    all_objects = models.Manager()

    def __str__(self):
        return '%s (%s)' % (self.dish, self.price)


class EnrollmentoptionFoodAnswer(EnrollmentoptionAnswer):
    dishprice = models.ForeignKey(DishPrice, null=True, blank=True, verbose_name=_l('Dish cost'), on_delete=models.PROTECT)

    @property
    def answer(self):
        return self.dishprice.dish if self.dishprice else None

    @property
    def display_answer(self):
        return self.answer or _l("(none)")

    def is_empty(self):
        return EnrollmentoptionFoodAnswer.objects.filter(id=self.id).filter(dishprice__isnull=True).exists()

    def get_price_extra(self) -> Decimal:
        return self.dishprice.price if self.dishprice else super(EnrollmentoptionFoodAnswer, self).get_price_extra()


class EventDeskRegistrationMessage(models.Model):
    class EventRegistrationStates(models.TextChoices):
        NEW = 'NEW', _l("Registered")
        ACCEPTED = 'ACCEPTED', _l("Accepted")
        UNKOWN = 'UNKNOWN', _l("Unknown")

    message_id = models.CharField(verbose_name=_l("E-mail message ID"), unique=True, max_length=191)
    message_date = models.DateTimeField(verbose_name=_l("E-mail message timestamp"))
    activity = models.ForeignKey(to=Activity, blank=True, null=True, on_delete=models.SET_NULL)
    state = models.CharField(verbose_name=_l("New state of the event registration"),
                             choices=EventRegistrationStates.choices, max_length=191)
    requester = models.CharField(verbose_name=_l("Person that requested the registration as stated in the e-mail"),
                                 max_length=191)
    event_name = models.CharField(verbose_name=_l("Name of the event as stated in the e-mail"), max_length=191)
    event_start = models.CharField(verbose_name=_l("Start date/time of the event as stated in the e-mail"), max_length=191)
    event_end = models.CharField(verbose_name=_l("End date/time of the event as stated in the e-mail"), max_length=191)
    event_location = models.CharField(verbose_name=_l("Location of the event as stated in the e-mail"), max_length=191)
    match_ratio = models.DecimalField(verbose_name=_l("Percentage certainty of match with activity."), decimal_places=3,
                                      max_digits=6, blank=True, null=True)

    class Meta:
        ordering = ['-message_date']

    def get_event_start(self):
        date_start = None
        try:
            date_start = make_aware(datetime.strptime(self.event_start, "%d %B %Y %H:%M"))
        except ValueError:
            pass
        try:
            # Change the locale to NL, because the months in registration e-mails might be in
            # Dutch and strptime cannot parse them otherwise.
            with setlocale(("nl_NL", "UTF-8")):
                date_start = make_aware(datetime.strptime(self.event_start, "%d %B %Y %H:%M"))
        except ValueError:
            pass
        return date_start

    def get_event_end(self):
        date_end = None
        try:
            date_end = make_aware(datetime.strptime(self.event_end, "%d %B %Y %H:%M"))
        except ValueError:
            pass
        try:
            # Change the locale to NL, because the months in registration e-mails might be in
            # Dutch and strptime cannot parse them otherwise.
            with setlocale(("nl_NL", "UTF-8")):
                date_end = make_aware(datetime.strptime(self.event_end, "%d %B %Y %H:%M"))
        except ValueError:
            pass
        return date_end

    def get_match_ratio_display(self):
        if self.match_ratio is None or self.match_ratio == -1:
            return _l("n/a")
        else:
            return _l("{0:.1f}% certain").format(self.match_ratio * 100)

    def ratio_ok(self):
        if self.match_ratio is None or self.match_ratio == -1:
            return None
        else:
            return self.match_ratio > 0.6


##
# Event hooks for Activities module
##
def createdishprice(sender, **kwargs):
    if kwargs['created']:
        instance = kwargs['instance']
        for dish in instance.restaurant.dish_set.all():
            dishprice = DishPrice(dish=dish, price=dish.price, question=instance)
            dishprice.save()


def updatewaitinglist(sender, **kwargs):
    instance: Activity = kwargs['instance']
    instance.update_waiting_list()


post_save.connect(createdishprice, sender=EnrollmentoptionFood)
post_save.connect(updatewaitinglist, sender=Activity)
post_save.connect(send_discord, sender=Activity)

# Pre-save hook for activity to send_discord to be able to check if pictures were added
pre_save.connect(send_discord_presave, sender=Activity)

@receiver(pre_delete, sender=Activity)
def pre_delete_cleanup_activity_participations(sender: Type[Activity] , instance: Activity, **kwargs):
    """
    Pre-delete hook as a final catch to make sure to unenroll everyone properly from an activity before it is deleted.
    This makes sure everyone gets a cancellation e-mail even if it is forgotten in the deleting party.
    However, ideally, this method (Activity.unenroll_all_participants) is called earlier with the actor argument set,
    so that it is recorded who deleted the activity and unenrolled the participants.
    """
    instance.unenroll_all_participants()

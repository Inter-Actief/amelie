from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Sum, Q
from django.urls import reverse
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.translation import get_language, gettext_lazy as _l
from oauth2_provider.models import Application

from amelie.activities.utils import setlocale, update_waiting_list
from amelie.files.models import Attachment
from amelie.calendar.managers import EventManager
from amelie.calendar.models import Event, Participation
from amelie.tools.ariana import send_irc
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
    maximum = models.PositiveIntegerField(blank=True, null=True)
    waiting_list_locked = models.BooleanField(default=False, verbose_name=_l('Lock waiting list'))

    photos = models.ManyToManyField(Attachment, blank=True, related_name='foto_set')
    components = models.ManyToManyField('self', blank=True)

    price = models.DecimalField(default="0.00", max_digits=8, decimal_places=2, verbose_name=_l('price'))
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

    @property
    def activity_type(self):
        return "regular"

    @property
    def confirmed_participants(self):
        return self.participants.filter(participation__waiting_list=False)

    @property
    def confirmed_participations(self):
        return self.participation_set.filter(waiting_list=False)

    @property
    def waiting_participants(self):
        return self.participants.filter(participation__waiting_list=True)

    @property
    def waiting_participations(self):
        return self.participation_set.filter(waiting_list=True)

    def clean(self):
        super(Activity, self).clean()

        if self.enrollment:
            if self.enrollment_begin is None:
                raise ValidationError(_l('There is no enrollment start date entered.'))

            if self.enrollment_end is None:
                raise ValidationError(_l('There is no enrollment end date entered.'))

    def get_absolute_url(self):
        return reverse('activities:activity', args=[self.id])

    def get_photo_url_random(self):
        return reverse('activities:random_photo', args=[self.id])

    def get_photo_url(self):
        return reverse('activities:gallery', args=[self.id])

    def get_calendar_url(self):
        return reverse('activities:ics', args=[self.id])

    def random_photo(self, only_public=True):
        photos = self.photos.filter_public(only_public)

        # Select a random photo
        photo = photos.order_by('?')[:1]

        # Done
        return photo[0] if len(photo) > 0 else None

    def random_public_photo(self):
        return self.random_photo(only_public=True)

    def enrollment_open(self):
        """Shows whether the enrollment is open at this time"""
        return self.enrollment_begin < timezone.now() < self.enrollment_end

    enrollment_open.boolean = True

    def enrollment_closed(self):
        """
        If True then the enrollment deadline is over thus you are too late to enroll.
        """

        return timezone.now() > self.enrollment_end

    def can_edit(self, person):
        """

        """

        return person.is_board() or (self.organizer in person.current_committees()) or person.user.is_superuser

    def places_available(self):
        """
        Calculates the number of available places.
        If there is no maximum, then the result of this function is None.
        """

        return max(0, self.maximum - self.participants.filter(participation__waiting_list=False).count()) if self.maximum else None

    def enrollment_full(self):
        """
        True if there are no more places available to enroll and if there is a maximum.
        """

        places_available = self.places_available()
        return places_available is not None and places_available == 0

    def has_waiting_participants(self):
        """
        True if there is a waiting list that is not empty.
        """
        return self.waiting_participants.count() > 0

    def enrollment_almost_full(self):
        """
        True if there are less than ten places available and if there is a maximum.
        """

        places_available = self.places_available()
        return places_available is not None and places_available <= 10

    def has_enrollmentoptions(self):
        return self.enrollmentoption_set.exists()

    def has_costs(self):
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

    def latest_event_registration_message(self):
        return self.eventdeskregistrationmessage_set.all().order_by('-message_date').first()


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

    price_extra = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price extra'), default=0)
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

    price_extra = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_l('Price extra'), default=0)
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

    def get_price_extra(self):
        """
        Calculate extra costs based on data
        """

        return 0


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

    def get_price_extra(self):
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

    def get_price_extra(self):
        return self.enrollmentoption.enrollmentoptionnumeric.price_extra * self.answer


class EnrollmentoptionSelectboxAnswer(EnrollmentoptionAnswer):
    answer = models.ForeignKey(SelectboxOption, verbose_name=_l('Respons'), on_delete=models.CASCADE)
    objects = SubclassManager()

    @property
    def display_answer(self):
        return self.answer or _l("(none)")

    def is_empty(self):
        return EnrollmentoptionSelectboxAnswer.objects.filter(id=self.id).filter(answer__isnull=True).exists()

    def get_price_extra(self):
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

    def get_price_extra(self):
        return self.dishprice.price if self.dishprice else super(EnrollmentoptionFoodAnswer, self).get_price_extra()


def createdishprice(sender, **kwargs):
    if kwargs['created']:
        instance = kwargs['instance']
        for dish in instance.restaurant.dish_set.all():
            dishprice = DishPrice(dish=dish, price=dish.price, question=instance)
            dishprice.save()


post_save.connect(createdishprice, sender=EnrollmentoptionFood)
# IRC notifications disabled because the bot is broken -- albertskja 2023-03-28
# post_save.connect(send_irc, sender=Activity)
post_save.connect(send_discord, sender=Activity)
post_save.connect(update_waiting_list, sender=Activity)

# Pre-save hook for activity to send_discord to be able to check if pictures were added
pre_save.connect(send_discord_presave, sender=Activity)


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

post_save.connect(update_waiting_list, Activity)

# -*- coding: utf-8 -*-

import datetime
import uuid

import os
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator, MaxValueValidator, \
    MinValueValidator
from django.db import models, transaction
from django.db.models import Q, F
from django.db.models.signals import post_save, m2m_changed
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _l

from amelie.claudia.mappable import Mappable
from amelie.claudia.tools import is_verifiable, verify_instance
from amelie.members.managers import PersonManager, CommitteeManager
from amelie.tools.encodings import normalize_to_ascii
from amelie.tools.logic import current_association_year
from amelie.tools.validators import CheckDigitValidator

LANGUAGE_CHOICES = [(l[0], _l(l[1])) for l in settings.LANGUAGES]


class Faculty(models.Model):
    """
    A faculty, e.g. EEMCS. Studies and research groups are linked using their respective models.
    Because of imports in the education module they are found in the members module.
    """
    name = models.CharField(max_length=100, verbose_name=_l('Name'))
    abbreviation = models.CharField(max_length=10, verbose_name=_l('Abbreviation'))

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('faculty')
        verbose_name_plural = _l('faculties')

    def __str__(self):
        return '%s (%s)' % (self.name, self.abbreviation)


class Department(models.Model):
    """
    A department can be either a research group (e.g. CAES) or a service (e.g. LISA).
    Because of imports in the education module they are found in the members module.
    """
    class DepartmentTypes(models.TextChoices):
        RESEARCH_GROUP = 'researchgroup', _l('Chair')
        SERVICE = 'service', _l('Service')

    name = models.CharField(max_length=100, verbose_name=_l('Name'))
    abbreviation = models.CharField(max_length=10, verbose_name=_l('Abbreviation'))
    faculty = models.ForeignKey(Faculty, null=True, blank=True, verbose_name=_l('Faculty'), on_delete=models.SET_NULL)
    type = models.CharField(max_length=15, choices=DepartmentTypes.choices, verbose_name=_l('Type'))

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('department')
        verbose_name_plural = _l('departments')

    def __str__(self):
        return '%s (%s)' % (self.name, self.abbreviation)


class Study(models.Model):
    """
    Study like Technical Computer Science. Studies can be Bachelor, Master or Engineering trainings.
    Because of imports in the education module they are found in the members module.
    """
    class StudyTypes(models.TextChoices):
        BSC = 'BSc', _l('Bachelor of Science')
        MSC = 'MSc', _l('Master of Science')
        IR = 'Ir', _l('Engineer')

    name_nl = models.CharField(max_length=100, verbose_name=_l('Name'))
    name_en = models.CharField(max_length=100, verbose_name=_l('Name (en)'), blank=True)
    abbreviation = models.CharField(max_length=10, verbose_name=_l('Abbreviation'))
    faculties = models.ManyToManyField(Faculty, verbose_name=_l('Faculties'))
    type = models.CharField(max_length=3, choices=StudyTypes.choices, verbose_name=_l('Type'))
    length = models.IntegerField(verbose_name=_l('Course length'))
    primary_study = models.BooleanField(
        default=False,
        verbose_name=_l("Primary study"),
        help_text=_l("Indicates that this study is one of our primary studies")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_l("Active"),
        help_text=_l("Make a study inactive when the study is not given any more on the University of Twente"),
    )

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    class Meta(object):
        ordering = ['abbreviation']
        verbose_name = _l('study')
        verbose_name_plural = _l('studies')

    def __str__(self):
        return '%s (%s)' % (self.name, self.abbreviation)


class Dogroup(models.Model):
    """
    A do-group such as these are created over the years:
    e.g. Tegel, TuinfeesT
    """
    name = models.CharField(verbose_name=_l('Name'), max_length=50)
    color = ColorField(verbose_name=_l('Color'), help_text=_l("What is the color of this dogroup?"),
                       default="#000000")

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('do-group')
        verbose_name_plural = _l('do-groups')

    def __str__(self):
        return self.name


class DogroupGeneration(models.Model, Mappable):
    """
    A generation of a dogroup (e.g. Tegel 2013). Please note that processing properties of this model may be subject to
    privacy regulations. Refer to https://privacy.ia.utwente.nl/ and check whether processing the property is allowed
    for your purpose.
    """
    generation = models.PositiveIntegerField(verbose_name=_l('Generation'))
    dogroup = models.ForeignKey(Dogroup, verbose_name=_l('Dogroup'), on_delete=models.PROTECT)
    parents = models.ManyToManyField('Person', verbose_name=_l('Introduction parents'), blank=True)
    study = models.ForeignKey(Study, verbose_name=_l('Course'), on_delete=models.PROTECT)
    mail_alias = models.EmailField(verbose_name=_l('Mailalias'))
    generation_color = ColorField(verbose_name=_l('Generation color'), blank=True, null=True,
                                  help_text=_l("Similar to the dogroup color, however this value can be set in order to override the color for just this generation"))

    class Meta(object):
        ordering = ['generation', 'dogroup']
        verbose_name = _l('do-group generation')
        verbose_name_plural = _l('do-group generations')

    @property
    def color(self):
        return self.generation_color if self.generation_color else self.dogroup.color

    def __str__(self):
        return '%s %s' % (self.dogroup, self.generation)

    def clean(self):
        super(DogroupGeneration, self).clean()
        if not any(self.mail_alias.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l(
                'The mail alias for a dogroup generation may only point to an Inter-Actief server.'
            )})

        from amelie.claudia.models import Mapping
        # Check if the email address is already in use!
        if self.mail_alias and Mapping.objects.filter(email=self.mail_alias).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.mail_alias)) > 1 or \
                Mapping.objects.get(email=self.mail_alias).get_mapped_object() != self:
                raise ValidationError({'email': _l(
                    'This email address is already in use by another mapping!'
                )})

    # ===== Methods for Claudia-mapping =====
    def get_name(self):
        """Get the full name of the do-group generation"""
        return self.__str__()

    def get_email(self):
        """Get the e-mail address of the do-group"""
        return self.mail_alias

    def is_active(self):
        """Is this do-group active?"""
        return bool(self.members())

    def is_dogroup(self):
        """Is this group a do-group? Yes."""
        return True

    def members(self, old_members=False):
        """Get members of this do-group.

        Only gives do-group members that are still member of the association, unless old_members is True.
        """
        persons = Person.objects

        if not old_members:
            persons = persons.members()

        # Do-group children
        children = persons.filter(student__studyperiod__dogroup=self, preferences__name='mail_dogroup')

        # Do-group parents
        parents = persons.filter(dogroupgeneration=self, preferences__name='mail_dogroup')

        return list(children) + list(parents)


class Association(models.Model):
    """
    Study assocation for secundary members (e.g. Scintilla).
    """
    name = models.CharField(max_length=100, verbose_name=_l('Name'))
    studies = models.ManyToManyField(Study, blank=True, verbose_name=_l('Courses'))

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('association')
        verbose_name_plural = _l('associations')

    def __str__(self):
        return '%s' % self.name


class PreferenceCategory(models.Model):
    """
    A category for preferences.
    """
    name = models.CharField(max_length=30, verbose_name=_l('Category of preference'))

    class Meta(object):
        verbose_name = _l('category of preference')
        verbose_name_plural = _l('categories of preference')

    def __str__(self):
        return '%s' % self.name


class Preference(models.Model):
    """
    Preference of a person, e.g. if they want the weekly mail.
    """
    name = models.CharField(max_length=30, verbose_name=_l('Name'))
    preference_nl = models.CharField(max_length=200, verbose_name=_l('Preference'))
    preference_en = models.CharField(max_length=200, verbose_name=_l('Preference(s)'))
    category = models.ForeignKey(PreferenceCategory, on_delete=models.PROTECT)
    default = models.BooleanField(default=False, verbose_name=_l('Standard'))
    adjustable = models.BooleanField(default=False, verbose_name=_l('Adjustable by the user in profile'))
    first_time = models.BooleanField(default=False, verbose_name=_l('Adjustable by the user on login'))
    print = models.BooleanField(default=False, verbose_name=_l('Print'))

    @property
    def preference(self):
        language = get_language()

        if language == "en" and self.preference_en:
            return self.preference_en
        else:
            return self.preference_nl

    class Meta(object):
        ordering = ['name', 'preference_nl']
        verbose_name = _l('preference')
        verbose_name_plural = _l('preference')

    def __str__(self):
        return '%s' % self.preference


def person_picture_upload_path(instance, filename):
    return os.path.join('profile_picture/', '{}.{}'.format(uuid.uuid4(), filename.split('.')[-1]))


class Person(models.Model, Mappable):
    """
    Person. This can either be a student, an employee, neither or not even a member.
    Model is also used to save teachers of courses, etc. Please note that processing properties of this model may be
    subject to privacy regulations. Refer to https://privacy.ia.utwente.nl/ and check whether processing the property is
    allowed for your purpose.
    """
    class GenderTypes(models.TextChoices):
        UNKNOWN = 'Unknown', _l('Unknown')
        MAN = 'Man', _l('Man')
        WOMAN = 'Woman', _l('Woman')
        OTHER = 'Other', _l('Other')

    class InternationalChoices(models.TextChoices):
        YES = 'Yes', _l('Yes, I am an international student.')
        NO = 'No', _l('No, I am not an international student.')
        UNKNOWN = 'Unknown', _l('I would rather not say if I\'m an international student or not.')

    class ShellChoices(models.TextChoices):
        DEFAULT = 'default', _l('No preference')
        BASH = 'bash', _l('Bash')
        ZSH = 'zsh', _l('Z shell')

    first_name = models.CharField(max_length=50, verbose_name=_l('First name'))
    last_name_prefix = models.CharField(max_length=25, blank=True, verbose_name=_l('Last name pre-fix'))
    last_name = models.CharField(max_length=50, verbose_name=_l('Last name'))
    initials = models.CharField(max_length=20, blank=True, verbose_name=_l('Initials'))
    slug = models.SlugField(max_length=150, editable=False)

    # Picture stores the 'real' profile picture, unverified_picture stores a new profile picture while the board has not checked it yet.
    picture = models.ImageField(upload_to=person_picture_upload_path, blank=True, null=True, verbose_name=_l('Photo'))
    unverified_picture = models.ImageField(upload_to=person_picture_upload_path, blank=True, null=True, verbose_name=_l('Unverified photo'))

    notes = models.TextField(blank=True, verbose_name=_l('Notes'))

    gender = models.CharField(max_length=9, choices=GenderTypes.choices, verbose_name=_l('Gender'))
    preferred_language = models.CharField(max_length=100, choices=LANGUAGE_CHOICES, default='nl',
                                          verbose_name=_l('Language of preference'))
    international_member = models.CharField(max_length=16, choices=InternationalChoices.choices,
                                            verbose_name=_l("International student"))

    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_l('Birth date'))

    email_address = models.EmailField(verbose_name=_l('E-mail address'), null=True)
    address = models.CharField(max_length=50, verbose_name=_l('Address'))
    postal_code = models.CharField(max_length=8, verbose_name=_l('Postal code'))
    city = models.CharField(max_length=30, verbose_name=_l('City'))
    country = models.CharField(max_length=25, default='Nederland', verbose_name=_l('Country'))
    telephone = models.CharField(max_length=20, blank=True, verbose_name=_l('Phonenumber'))

    email_address_parents = models.EmailField(verbose_name=_l('E-mail address of parent(s)/guardian(s)'), blank=True)
    address_parents = models.CharField(max_length=50, blank=True, verbose_name=_l('Address of parent(s)/guardian(s)'))
    postal_code_parents = models.CharField(max_length=8, blank=True,
                                           verbose_name=_l('Postal code of parent(s)/guardian(s)'))
    city_parents = models.CharField(max_length=30, blank=True,
                                    verbose_name=_l('Residence of parent(s)/guardian(s)'))
    country_parents = models.CharField(max_length=25, blank=True, default='Nederland',
                                       verbose_name=_l('Country of parent(s)/guardian(s)'))
    can_use_parents_address = models.BooleanField(default=False, verbose_name=_l("My parents' address details may be "
                                                                                "used for the parents day."))

    account_name = models.CharField(max_length=50, blank=True, verbose_name=_l('Account name'), validators=[
        RegexValidator(r'^[a-z]*$', _l('You can only enter ^[a-z]*$.'), _l('Invalid account name')),
        MinLengthValidator(2),
        MaxLengthValidator(20),
    ])
    ut_external_username = models.CharField(
        max_length=8, blank=True, null=True, verbose_name=_l('UT external account name'), validators=[
            RegexValidator(r'^x[0-9]{7}$', _l('You can only enter ^x[0-9]{7}$.'), _l('Invalid account name'))
        ]
    )
    shell = models.CharField(max_length=10, choices=ShellChoices.choices, default=ShellChoices.DEFAULT, verbose_name=_l('Unix shell'))
    webmaster = models.BooleanField(default=False, verbose_name=_l('Is web master'))
    nda = models.BooleanField(default=False, verbose_name=_l('Has signed NDA'))

    preferences = models.ManyToManyField(Preference, blank=True, verbose_name=_l('Preferences'))
    user = models.OneToOneField(User, null=True, blank=True, related_name='person', verbose_name=_l('User'),
                                on_delete=models.SET_NULL)

    password_reset_code = models.CharField(max_length=50, verbose_name=_l("Password reset code"),
                                           null=True, blank=True, unique=True, editable=False)
    password_reset_expiry = models.DateTimeField(verbose_name=_l('Password reset code expiry'),
                                                 null=True, blank=True, editable=False)

    sudo_reset_code = models.CharField(max_length=50, verbose_name=_l("Sudo password reset code"),
                                       null=True, blank=True, unique=True, editable=False)
    sudo_reset_expiry = models.DateTimeField(verbose_name=_l('Sudo password reset code expiry'),
                                             null=True, blank=True, editable=False)

    objects = PersonManager()

    class Meta(object):
        ordering = ['last_name']
        verbose_name = _l('person')
        verbose_name_plural = _l('people')

    def __str__(self):
        return self.incomplete_name()

    def save(self, force_insert=False, **kwargs):
        self.slug = slugify(self.__str__())
        super(Person, self).save()

    save.alters_data = True  # template security

    def has_user(self):
        return self.user is not None

    has_user.boolean = True

    def get_or_create_user(self, username):
        created = False
        if self.user:
            return self.user, created  # person is already known
        else:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                user = User(username=username)  # create user for person
                user.save()
                created = True
            self.user = user
            self.save()
            return user, created

    def is_employee(self):
        return hasattr(self, 'employee')

    def is_student(self):
        return hasattr(self, 'student')

    def is_active_member(self):
        return self.function_set.filter(end__isnull=True, committee__abolished__isnull=True).exists()

    is_active_member.boolean = True

    def is_member_strict(self):
        member = self.membership_set.filter(Q(type__price=0) | Q(payment__isnull=False),
                                            year=current_association_year())
        member = member.filter(models.Q(ended__isnull=True) | models.Q(ended__gt=datetime.date.today()))
        return member.count() > 0

    is_member_strict.boolean = True

    def is_member(self):
        return self.membership is not None

    is_member.boolean = True

    def is_board(self):
        return self.function_set.filter(committee__superuser=True, committee__abolished__isnull=True,
                                        end__isnull=True).exists()

    def is_in_committee(self, abbreviation):
        return self.function_set.filter(committee__abbreviation=abbreviation, end__isnull=True).exists()

    def is_room_duty(self):
        return self.is_in_committee(settings.ROOM_DUTY_ABBREVIATION)

    is_board.boolean = True

    def was_board_at(self, dt):
        return self.function_set.filter(
            Q(committee__superuser=True),
            Q(committee__abolished__isnull=True) | Q(committee__abolished__gt=dt),
            Q(committee__founded__isnull=False),
            Q(committee__founded__lte=dt),
            Q(end__isnull=True) | Q(end__gt=dt),
            Q(begin__isnull=False),
            Q(begin__lte=dt)
        ).exists()

    was_board_at.boolean = True

    def is_candidate_board(self):
        try:
            cb = Committee.objects.get(abbreviation="KB", abolished__isnull=True)
            return self.function_set.filter(committee__parent_committees=cb, end__isnull=True,
                                            committee__abolished__isnull=True).exists()
        except Committee.DoesNotExist:
            return False

    is_candidate_board.boolean = True

    def is_education_committee(self):
        return self.function_set.filter(committee=Committee.education_committee(), end__isnull=True).exists()

    is_education_committee.boolean = True

    def full_name(self):
        first_name = self.first_name
        if not self.first_name and self.initials:
            first_name = self.initials
        elif self.initials:
            first_name = '%s (%s)' % (first_name, self.initials)
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def incomplete_name(self):
        first_name = self.first_name
        if not self.first_name and self.initials:
            first_name = self.initials
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def initials_last_name(self):
        """
        Gives the initials and last name of this person.
        Uses the person's first name if no initials are known.
        """
        first_name = self.initials
        if not self.initials and self.first_name:
            first_name = self.first_name
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def current_committees(self):
        """
        Returns a queryset with all committees this person is currently in.
        For the Board and developers (is_staff) you get a list of all active committees.
        """
        return Committee.objects.filter(function__person=self, function__end__isnull=True, abolished__isnull=True)

    def current_committees_at(self, dt):
        """
        Returns a queryset with all committees this person was in on the given date.
        For the Board and developers (is_staff) you get a list of all active committees.
        """
        return Committee.objects.filter(
            Q(function__person=self),
            Q(function__end__isnull=True) | Q(function__end__gt=dt),
            Q(function__begin__isnull=False),
            Q(function__begin__lte=dt),
            Q(abolished__isnull=True) | Q(abolished__gt=dt),
            Q(founded__isnull=False),
            Q(founded__lte=dt)
        )

    def age(self, at=None):
        """
        Returns the age of a person, on a given specific data
        """
        if at is None:
            at = datetime.date.today()
        if self.date_of_birth is not None:
            not_this_year_yet = (at.month, at.day) < (self.date_of_birth.month, self.date_of_birth.day)
            return at.year - self.date_of_birth.year - not_this_year_yet
        else:
            return None

    def has_preference(self, name=None, preference=None, default=False):
        try:
            if preference is None:
                preference = Preference.objects.get(name=name)

            return preference in self.preferences.all()
        except Preference.DoesNotExist:
            return default

    def has_mandate(self, mandate_type):
        """
        Returns if this person has an active mandate for the requested mandate type.

        Mandate type can be: contribution, consumptions, activities, or other_payments

        See amelie.personal_tab.models.AuthorizationType
        """
        kwargs = {'authorization_type__%s' % mandate_type: True}
        return self.authorization_set.filter(is_signed=True,
                                             end_date__isnull=True, **kwargs)

    def has_mandate_contribution(self):
        """
        Returns if this person has an active mandate for contribution.
        """
        return self.has_mandate('contribution')

    def has_mandate_consumptions(self):
        """
        Returns if this person has an active mandate for consumptions.
        """
        return self.has_mandate('consumptions')

    def has_mandate_activities(self):
        """
        Returns if this person has an active mandate for activities.
        """
        return self.has_mandate('activities')

    def has_mandate_other_payments(self):
        """
        Returns if this person has an active mandate for other payments.
        """
        return self.has_mandate('other_payments')

    def oauth_consumer_set(self):
        consumers = {}
        for auth in self.oauth_authorization_set.order_by('-last_use').all():
            if auth.consumer in consumers:
                consumers[auth.consumer].append(auth)
            else:
                consumers[auth.consumer] = [auth]
        return consumers

    @property
    def membership(self):
        """
        Get the active Membership object for this year. If there is no active membership, this function returns None.
        """
        membership = self.membership_set.filter(year=current_association_year())
        membership = membership.filter(models.Q(ended__isnull=True) | models.Q(ended__gt=datetime.date.today()))

        return membership[0] if len(membership) > 0 else None

    def get_absolute_url(self):
        return reverse('members:person_view', args=(), kwargs={'id': self.pk, 'slug': self.slug, })

    @staticmethod
    def search(query, option):
        if query:
            return Person.objects.filter(*[Q(slug__icontains=z.lower()) for z in query.split(' ') if len(z) > 2])
        else:
            return []

    # ===== Methods for Claudia-mapping =====
    def get_name(self):
        """Get incomplete name for this person"""
        return self.incomplete_name()

    def get_givenname(self):
        """Get first name for this person"""
        return self.first_name

    def get_surname(self):
        """Get last name prefix and last name for this person"""
        if self.last_name_prefix:
            return ' '.join([self.last_name_prefix, self.last_name])
        else:
            return self.last_name

    def get_adname(self):
        """Get Active Directory name for this person"""
        return self.account_name

    def get_email(self):
        """Get e-mail address for this person"""
        return self.email_address

    def get_extra_data(self):
        """Get extra data for this person"""
        return {
            'employee_number': self.employee.employee_number() if self.is_employee() else None,
            'student_number': self.student.student_number() if self.is_student() else None,
            'rfids': [rfid.code for rfid in self.rfidcard_set.filter(active=True)],
            'consumption_mandate': bool(self.is_member() and self.has_mandate_consumptions()),
            'preferred_language': self.preferred_language,
            'shell': self.shell if self.shell != 'default' else settings.CLAUDIA_SHELL_DEFAULT,
        }

    def is_needed(self):
        """
        Does this object need a Claudia Mapping?

        A mapping (in addition to the normal conditions) is also necessary if someone has a consumption mandate
        and RFID cards, because they have to be synchronized to Alexia.
        """
        return super(Person, self).is_needed() or (self.is_member() and self.has_mandate_consumptions()
                                                   and self.rfidcard_set.exists())

    def is_active(self):
        """Is this member an active member?"""
        return self.is_active_member()

    def is_webmaster(self):
        """Is this member a webmaster?"""
        return self.webmaster

    def personal_aliases(self):
        """
        Gives the e-mail aliases that this person could get.
        e.g. kevin.alberts or sebastiaan.denboer
        """
        if not self.is_active():
            return []

        # Strip spaces and apostrophes
        last_name = normalize_to_ascii(self.get_surname()).replace(' ', '').replace("'", '')
        name = normalize_to_ascii(self.get_givenname()).replace(' ', '').replace("'", '')
        return [('%s.%s' % (name, last_name)).lower()]

    def groups(self):
        """Get all groups of this person"""
        # Committees
        committees = Committee.objects.filter(abolished__isnull=True, function__person=self, function__end__isnull=True)

        # Do-groups
        if hasattr(self, 'student') and self.has_preference(name='mail_dogroup') and self.is_member():
            dogroups_child = DogroupGeneration.objects.filter(studyperiod__student=self.student)
            dogroups_parent = DogroupGeneration.objects.filter(parents=self)
        else:
            dogroups_child = []
            dogroups_parent = []

        return list(committees) + list(dogroups_child) + list(dogroups_parent)

    def clean(self):
        for domain in settings.IA_MAIL_DOMAIN:
            if self.email_address and self.email_address.endswith(domain):
                if any(alias + domain == self.email_address for alias in self.personal_aliases()) \
                        or self.get_adname() + domain == self.email_address:
                    raise ValidationError({'email_address': _l(
                        'Your email address is not to point to an Inter-Actief server. If you have a Google Apps '
                        'account please use firstname.lastname@gapps.inter-actief.nl as an alternative.'
                    )})


class MembershipType(models.Model):
    """
    A membership type, e.g. Primary member, Studylong member, USW.
    """
    name_nl = models.CharField(max_length=30, unique=True, verbose_name=_l('Name'))
    name_en = models.CharField(max_length=30, verbose_name=_l('Name (en)'), blank=True)
    description = models.TextField(null=True, blank=True, verbose_name=_l('Description'))
    price = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_l('Price'))
    needs_verification = models.BooleanField(default=False, verbose_name=_l('Needs verification'))

    active = models.BooleanField(default=True, verbose_name=_l('Active'))
    """If a membership type is active new memberships of this type can be created."""

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    class Meta(object):
        ordering = ['description']
        verbose_name = _l('membership type')
        verbose_name_plural = _l('membership types')

    def __str__(self):
        return '{} (€{})'.format(self.name, self.price)

class PaymentType(models.Model):
    """
    e.g. Cash or Debit transaction
    """
    name = models.CharField(max_length=20, unique=True, verbose_name=_l('Name'))
    description = models.TextField(verbose_name=_l('Description'))

    class Meta(object):
        ordering = ['description']
        verbose_name = _l('way of payment')
        verbose_name_plural = _l('ways of payment')

    def __str__(self):
        return '%s' % self.description


class Student(models.Model):
    """
    Student linked to a Person (or not). Actually only saves a number and other models (like StudyPeriod) link to this.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    person = models.OneToOneField(Person, verbose_name=_l('Person'), on_delete=models.CASCADE)
    number = models.PositiveIntegerField(verbose_name=_l('Student number'), null=True, blank=True, unique=True,
                                         validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])

    class Meta(object):
        verbose_name = _l('student')
        verbose_name_plural = _l('students')

    def __str__(self):
        if self.number is not None:
            return '%s (%s)' % (self.person, self.student_number())
        else:
            return '%s (-)' % self.person

    def student_number(self):
        if self.number is not None:
            return 's%07d' % self.number

    def enrolled_in_primary_study(self):
        return self.studyperiod_set.filter(graduated=False, end__isnull=True,
                                           study__primary_study=True).count() > 0


class StudyPeriod(models.Model):
    """
    A study that a student is/has enrolled in in a given period. Used to save studies of people. Please note that
    processing properties of this model may be subject to privacy regulations. Refer to https://privacy.ia.utwente.nl/
    and check whether processing the property is allowed for your purpose.
    """
    student = models.ForeignKey(Student, verbose_name=_l('Student'), on_delete=models.CASCADE)
    study = models.ForeignKey(Study, verbose_name=_l('Course'), on_delete=models.PROTECT)
    begin = models.DateField(verbose_name=_l('Begin'))
    end = models.DateField(null=True, blank=True, verbose_name=_l('End'))
    graduated = models.BooleanField(default=False, verbose_name=_l('Has graduated'))
    dogroup = models.ForeignKey(DogroupGeneration, null=True, blank=True, verbose_name=_l('Dogroup'),
                                on_delete=models.SET_NULL)

    class Meta(object):
        verbose_name = _l('study period')
        verbose_name_plural = _l('study periods')

    def __str__(self):
        return '%s, %s (%s-%s)' % (self.student, self.study, self.begin, self.end)


class Employee(models.Model):
    """
    Data about employee, this model is linked to Person. Please note that processing properties of this model may be
    subject to privacy regulations. Refer to https://privacy.ia.utwente.nl/ and check whether processing the property is
    allowed for your purpose.
    """
    person = models.OneToOneField(Person, verbose_name=_l('Person'), on_delete=models.CASCADE)
    number = models.PositiveIntegerField(blank=True, null=True, unique=True, verbose_name=_l('Employee number'),
                                         validators=[MinValueValidator(7640000), MaxValueValidator(9999999)])
    end = models.DateField(null=True, blank=True, verbose_name=_l('End'))

    class Meta(object):
        ordering = ['number']
        verbose_name = _l('employee')
        verbose_name_plural = _l('employees')

    def __str__(self):
        if self.number is not None:
            return '%s (m%07d)' % (self.person, self.number)
        else:
            return '%s (-)' % self.person

    def employee_number(self):
        if self.number is not None:
            return 'm%07d' % self.number


class Photographer(models.Model):
    """
    A photographer is someone that is the author of a picture on the IA site. But not a member of the association
    itself. In order to prevent unnecessary data collection this type of account only stores the first- and lastname of
    a person.
    """
    first_name = models.CharField(max_length=50, blank=True, verbose_name=_l('First name'), null=True)
    last_name_prefix = models.CharField(max_length=25, blank=True, verbose_name=_l('Last name pre-fix'), null=True)
    last_name = models.CharField(max_length=50, blank=True, verbose_name=_l('Last name'), null=True)
    person = models.OneToOneField(Person, on_delete=models.CASCADE, null=True, blank=True)

    def clean(self):
        """
        Make sure that if a photographer is not a person that the first- and lastname are known.
        """
        super(Photographer, self).clean()
        if self.person is not None:
            return
        if (self.first_name is not None and self.last_name is None) or (self.first_name is None and self.last_name is not None):
            raise ValidationError(_l('External photographers should at least have a first- and lastname.'))

    def __str__(self):
        if self.person is not None:
            return str(self.person)
        elif self.first_name is not None:
            if self.last_name_prefix is None:
                return f'{self.first_name} {self.last_name}'
            else:
                return f'{self.first_name} {self.last_name_prefix} {self.last_name}'


class Membership(models.Model):
    """
    A membership in a certain year. The membership is not valid if there is no payment, but there
    are also membership types where no payment is required (e.g. Honorary Member). Finally, a
    membership can be terminated by the member. If this is the case, the membership stops and
    any mandates the person might have can (should) no longer be used.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    member = models.ForeignKey(Person, verbose_name=_l('Member'), on_delete=models.PROTECT)
    type = models.ForeignKey(MembershipType, verbose_name=_l('Type'), on_delete=models.PROTECT)
    year = models.PositiveIntegerField(verbose_name=_l('Year'))
    ended = models.DateField(null=True, blank=True, verbose_name=_l('Ended preliminary'))
    verified_on = models.DateField(null=True, blank=True, verbose_name=_l('Verified on'))

    class Meta(object):
        ordering = ['member', 'year']
        verbose_name = _l('membership')
        verbose_name_plural = _l('memberships')

    def __str__(self):
        return '%s (%s, %s)' % (self.member, self.year, self.type)

    def is_paid(self):
        try:
            return self.payment
        except Payment.DoesNotExist:
            return self.type.price == 0

    def is_verified(self):
        if self.type.needs_verification and self.member.membership_set.filter(ended__isnull=True, year=current_association_year()+1).count() == 0:
            return self.verified_on is not None
        return True

    def verify(self):
        self.verified_on = datetime.date.today()
        self.save()

class Payment(models.Model):
    """
    Payment of a Membership.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    date = models.DateField(null=True, verbose_name=_l('Date'))
    payment_type = models.ForeignKey(PaymentType, verbose_name=_l('Payment'), on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_l('Price'))

    membership = models.OneToOneField(Membership, verbose_name=_l('Membership'), on_delete=models.PROTECT)

    class Meta(object):
        ordering = ['date']
        verbose_name = _l('payment')
        verbose_name_plural = _l('payments')

    def __str__(self):
        return '%s (%.2f)' % (self.membership, self.amount)


class CommitteeCategory(models.Model):
    """
    Category in which a committee can be placed (e.g. Activity committees).
    """
    name = models.CharField(max_length=50, verbose_name=_l('Name'))
    slug = models.SlugField(max_length=50, editable=False)

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('committee category')
        verbose_name_plural = _l('committee categories')

    def __str__(self):
        return '%s' % self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(CommitteeCategory, self).save(*args, **kwargs)

    save.alters_data = True  # template security


class Committee(models.Model, Mappable):
    """
    Committee of the association. Members are connected via a Function and if the function changes,
    a *new* Function object is created.
    """
    name = models.CharField(max_length=100, verbose_name=_l('Name'))
    abbreviation = models.CharField(max_length=20, unique=True, verbose_name=_l('Abbreviation'), validators=[
        RegexValidator(r'^[a-zA-Z0-9.-]*$', _l('You can only enter ^[a-zA-Z0-9.-]*$.'), _l('Invalid account name')),
        MinLengthValidator(2), MaxLengthValidator(20),
    ])
    category = models.ForeignKey(CommitteeCategory, null=True, blank=True, verbose_name=_l('Category'),
                                 on_delete=models.SET_NULL)
    parent_committees = models.ManyToManyField('self', blank=True, verbose_name=_l('Parent committees'),
                                               symmetrical=False)

    slug = models.SlugField(max_length=100, editable=False)

    email = models.EmailField(blank=True, verbose_name=_l('E-mail address'))
    founded = models.DateField(verbose_name=_l('Started on'), auto_now_add=True)
    abolished = models.DateField(null=True, blank=True, verbose_name=_l('Ended on'))
    website = models.URLField(blank=True, verbose_name=_l('Web site'))
    information_nl = models.TextField(verbose_name=_l('Information'))
    information_en = models.TextField(verbose_name=_l('Information (en)'))

    private_email = models.BooleanField(default=False, verbose_name=_l('E-mail address is private'),
                                        help_text=_l(
                                            'The e-mail address of this committee is not displayed on the website'))

    superuser = models.BooleanField(default=False, verbose_name=_l('Is board'),
                                    help_text=_l(
                                        'Members of this committee are granted board authorities on this web site'))

    gitlab = models.BooleanField(default=False, verbose_name=_l('Create GitLab group'),
                                 help_text=_l('Members of this committee get access to GitLab'))

    objects = CommitteeManager()

    logo = models.ImageField(upload_to='logos', null=True, blank=True)

    group_picture = models.ImageField(upload_to='committeeGroupPictures', null=True, blank=True)

    ledger_account_number = models.CharField(max_length=8, verbose_name=_l('ledger account'), default='2500')

    class Meta(object):
        ordering = ['name']
        verbose_name = _l('committee')
        verbose_name_plural = _l('committees')

    def __str__(self):
        return '%s' % self.name

    def clean(self):
        super(Committee, self).clean()
        if not any(self.email.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l(
                'The email address for a committee may only point to an Inter-Actief server.'
            )})

        from amelie.claudia.models import Mapping
        # Check if the email address is already in use!
        if self.email and Mapping.objects.filter(email=self.email).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.email)) > 1 or Mapping.objects.get(email=self.email).get_mapped_object() != self:
                raise ValidationError({'error': _l(
                    'This email address is already in use by another mapping!'
                )})

    def save(self, *args, **kwargs):
        self.slug = slugify(self.__str__())
        super(Committee, self).save(*args, **kwargs)

    save.alters_data = True  # template security

    def is_parent_committee(self):
        return self.committee_set.exists()

    def get_logo(self):
        if self.logo is not None:
            return self.logo

        for committee in self.parent_committees.all():
            logo = committee.get_logo()

            if logo is not None:
                return logo

        return None

    def get_absolute_url(self):
        return reverse('members:committee', args=(), kwargs={'id': self.pk, 'slug': self.slug, })

    def get_random_picture_url(self):
        return reverse('members:random_picture', args=(), kwargs={'id': self.pk, 'slug': self.slug, })

    @staticmethod
    def education_committee():
        try:
            return Committee.objects.get(abbreviation=settings.EDUCATION_COMMITTEE_ABBR)
        except Committee.DoesNotExist:
            return None

    # ===== Methods for Claudia-mapping =====
    def get_name(self):
        """Get full name of the committee"""
        return self.name

    def get_adname(self):
        """Get Active Directory name of the committee"""
        return self.abbreviation

    def get_email(self):
        """Get e-mail address of committee"""
        return self.email

    def is_active(self):
        """Does this committee need an account?"""
        return not self.abolished

    def is_committee(self):
        """Is this object a committee? Yes."""
        return True

    def get_extra_data(self):
        """Get extra data of this committee"""
        return {
            'gitlab': self.gitlab,
        }

    def members(self, old_members=False):
        """
        Get members of this committee.
        Please note that processing this property may be subject to privacy regulations. Refer to
        https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
        """
        if old_members:
            # Also include old members of this committee
            members = Person.objects.filter(function__committee=self)
        else:
            if self.abolished:
                # Committee abolished, no members
                return []
            else:
                members = Person.objects.filter(function__committee=self, function__end__isnull=True)
        child_committees = self.committee_set.filter(abolished__isnull=True)
        return list(members) + list(child_committees)

    def groups(self):
        """Give the parent committees of this committee"""
        if self.abolished:
            # Committee abolished, no parent committees
            return []
        return list(self.parent_committees.filter(abolished__isnull=True))

    @property
    def information(self):
        language = get_language()

        if language == "en":
            return self.information_en
        else:
            return self.information_nl


class Function(models.Model):
    """
    Function within a committee.
    Please note that processing properties of this model may be subject to privacy regulations. Refer to
    https://privacy.ia.utwente.nl/ and check whether processing the property is allowed for your purpose.
    """
    person = models.ForeignKey(Person, verbose_name=_l('Person'), on_delete=models.CASCADE)
    committee = models.ForeignKey(Committee, verbose_name=_l('Committee'), on_delete=models.CASCADE)
    function = models.CharField(max_length=75, verbose_name=_l('Position'))
    note = models.TextField(blank=True, verbose_name=_l('Remarks'))
    begin = models.DateField(verbose_name=_l('Started on'))
    end = models.DateField(null=True, blank=True, verbose_name=_l('Ended on'))

    class Meta(object):
        ordering = [F("end").desc(nulls_first=True), '-begin', 'person']
        verbose_name = _l('position')
        verbose_name_plural = _l('functions')

    def __str__(self):
        return '%s (%s, %s)' % (self.person, self.committee, self.function)

    def clean(self, *args, **kwargs):
        if self.pk:
            if not self.end and Function.objects.filter(person=self.person, end=None, committee=self.committee).exclude(
                    id=self.pk).exists():
                raise ValidationError(_l("Person is already a member of this committee."))
        else:
            if not self.end and Function.objects.filter(person=self.person, end=None,
                                                        committee=self.committee).exists():
                raise ValidationError(_l("Person is already a member of this committee."))

                # save.alters_data = True  # template security


class UnverifiedEnrollment(models.Model):
    # Person details
    first_name = models.CharField(max_length=50, verbose_name=_l('First name'))
    last_name_prefix = models.CharField(max_length=25, blank=True, verbose_name=_l('Last name pre-fix'))
    last_name = models.CharField(max_length=50, verbose_name=_l('Last name'))
    initials = models.CharField(max_length=20, blank=True, verbose_name=_l('Initials'))
    gender = models.CharField(max_length=9, choices=Person.GenderTypes.choices, verbose_name=_l('Gender'))
    preferred_language = models.CharField(max_length=100, choices=LANGUAGE_CHOICES, default='nl',
                                          verbose_name=_l('Language of preference'))
    international_member = models.CharField(max_length=16, choices=Person.InternationalChoices.choices,
                                            verbose_name=_l("International student"))
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_l('Birth date'))
    email_address = models.EmailField(verbose_name=_l('E-mail address'), null=True)
    address = models.CharField(max_length=50, verbose_name=_l('Address'))
    postal_code = models.CharField(max_length=8, verbose_name=_l('Postal code'))
    city = models.CharField(max_length=30, verbose_name=_l('City'))
    country = models.CharField(max_length=25, default='Nederland', verbose_name=_l('Country'))
    telephone = models.CharField(max_length=20, blank=True, verbose_name=_l('Phonenumber'))

    email_address_parents = models.EmailField(verbose_name=_l('E-mail address of parent(s)/guardian(s)'), blank=True)
    address_parents = models.CharField(max_length=50, blank=True, verbose_name=_l('Address of parent(s)/guardian(s)'))
    postal_code_parents = models.CharField(max_length=8, blank=True,
                                           verbose_name=_l('Postal code of parent(s)/guardian(s)'))
    city_parents = models.CharField(max_length=30, blank=True,
                                    verbose_name=_l('Residence of parent(s)/guardian(s)'))
    country_parents = models.CharField(max_length=25, blank=True, default='Nederland',
                                       verbose_name=_l('Country of parent(s)/guardian(s)'))
    can_use_parents_address = models.BooleanField(default=False, verbose_name=_l("My parents' address details may be "
                                                                                "used for the parents day."))
    preferences = models.ManyToManyField(Preference, blank=True, verbose_name=_l('Preferences'))

    # Authorizations that this person wants
    authorizations = models.ManyToManyField('personal_tab.Authorization', blank=True, verbose_name=_l('Authorizations'))

    # Membership details
    membership_type = models.ForeignKey(MembershipType, verbose_name=_l("Chosen membership type"),
                                        on_delete=models.PROTECT)
    membership_year = models.PositiveIntegerField(verbose_name=_l('Membership start year'))

    # Student details
    student_number = models.PositiveIntegerField(verbose_name=_l('Student number'), null=True, blank=True, unique=True,
                                                 validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])
    studies = models.ManyToManyField(Study, blank=True, verbose_name=_l('Studies'))
    study_start_date = models.DateField(verbose_name=_l('Study start date'))
    dogroup = models.ForeignKey(DogroupGeneration, null=True, blank=True, verbose_name=_l('Dogroup'),
                                on_delete=models.SET_NULL)

    def __str__(self):
        return "Unverified enrollment for '{} {}' of dogroup '{}'".format(self.first_name, self.last_name, self.dogroup)

    @transaction.atomic
    def activate_registration(self):
        # Import is here because of a circular import between members and personal_tab
        from amelie.personal_tab.models import Authorization, AuthorizationType

        # Construct the Person object
        person = Person(
            first_name=self.first_name,
            last_name_prefix=self.last_name_prefix,
            last_name=self.last_name,
            initials=self.initials,
            gender=self.gender,
            preferred_language=self.preferred_language,
            international_member=self.international_member,
            date_of_birth=self.date_of_birth,
            address=self.address,
            postal_code=self.postal_code,
            city=self.city,
            country=self.country,
            email_address=self.email_address,
            telephone=self.telephone,
            address_parents=self.address_parents,
            postal_code_parents=self.postal_code_parents,
            city_parents=self.city_parents,
            country_parents=self.country_parents,
            email_address_parents=self.email_address_parents,
            can_use_parents_address=self.can_use_parents_address,
        )
        person.save()

        # Preferences (m2m relations) can only be added after a person has been saved.
        person.preferences.set(self.preferences.all())
        person.save()

        # Add contribution authorization if wanted
        if self.authorization_contribution:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=person,
                iban=self.iban,
                bic=self.bic,
                account_holder_name=person.initials_last_name(),
                start_date=self.authorization_date
            )
            contribution_authorization.save()

        # Add other authorization if wanted
        if self.authorization_other:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=person,
                iban=self.iban,
                bic=self.bic,
                account_holder_name=person.initials_last_name(),
                start_date=self.authorization_date)
            authorization_other.save()

        # Add membership details
        membership = Membership(member=person, type=self.membership_type,
                                year=current_association_year())
        membership.save()

        # Add student details
        student = Student(person=person, number=self.student_number)
        student.save()

        # Add study periods
        for study in self.studies.all():
            study_period = StudyPeriod(student=student, study=study,
                                       begin=self.study_start_date,
                                       dogroup=self.dogroup)
            study_period.save()

        self.delete()

        return person

    def full_name(self):
        first_name = self.first_name
        if not self.first_name and self.initials:
            first_name = self.initials
        elif self.initials:
            first_name = '%s (%s)' % (first_name, self.initials)
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def incomplete_name(self):
        first_name = self.first_name
        if not self.first_name and self.initials:
            first_name = self.initials
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def initials_last_name(self):
        """
        Gives the initials and last name of this person.
        Uses the person's first name if no initials are known.
        """
        first_name = self.initials
        if not self.initials and self.first_name:
            first_name = self.first_name
        if self.last_name_prefix:
            return ' '.join([first_name, self.last_name_prefix, self.last_name])
        else:
            return ' '.join([first_name, self.last_name])

    def sortable_name(self):
        first_name = self.first_name
        if not self.first_name and self.initials:
            first_name = self.initials
        return ', '.join([self.last_name, first_name])


#
# Claudia-hooks
#
def _complain_with_claudia(sender, **kwargs):
    instance = kwargs.get('instance')
    if sender == Function:
        verify_instance(instance=instance.person)
    elif sender == StudyPeriod:
        verify_instance(instance=instance.student.person)


def _complain_with_claudia_m2m(sender, **kwargs):
    # Example:
    #   toppings = models.ManyToManyField(Topping)
    #   p.toppings.add(t)
    # Argument    Value
    # sender      Pizza.toppings.through (the intermediate m2m class)
    # instance    p (the Pizza instance being modified)
    # action      "pre_add" (followed by a separate signal with "post_add")
    # reverse     False (Pizza contains the ManyToManyField, so this call modifies the forward relation)
    # model       Topping (the class of the objects added to the Pizza)
    # pk_set      [t.id] (since only Topping t was added to the relation)

    instance = kwargs.get('instance')
    if is_verifiable(instance):
        verify_instance(instance=instance)

    pk_set = kwargs.get('pk_set')
    if pk_set:
        model = kwargs.get('model')
        objs = model.objects.filter(pk__in=pk_set)

        for obj in objs:
            if is_verifiable(obj):
                verify_instance(instance=obj)


post_save.connect(verify_instance, Person)
post_save.connect(verify_instance, Committee)
post_save.connect(verify_instance, DogroupGeneration)

post_save.connect(_complain_with_claudia, sender=Function)
post_save.connect(_complain_with_claudia, sender=StudyPeriod)

m2m_changed.connect(_complain_with_claudia_m2m, sender=Person.preferences.through)
m2m_changed.connect(_complain_with_claudia_m2m, sender=DogroupGeneration.parents.through)
m2m_changed.connect(_complain_with_claudia_m2m, sender=Committee.parent_committees.through)

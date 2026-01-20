# -*- coding: utf-8 -*-
import datetime
import csv
import os
from datetime import date
from difflib import SequenceMatcher

import re

from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q, TextChoices
from django.forms import widgets
from django.forms.models import BaseInlineFormSet
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _
from localflavor.generic.forms import BICFormField, IBANFormField

from amelie.tools.const import TaskPriority
from amelie.iamailer.mailtask import MailTask, Recipient
from amelie.style.forms import inject_style
from amelie.members.models import Department, PaymentType, Committee, CommitteeCategory, DogroupGeneration, \
    Function, Membership, MembershipType, Employee, Person, Student, Study, StudyPeriod, Preference, \
    LANGUAGE_CHOICES, UnverifiedEnrollment
from amelie.personal_tab.models import Authorization, AuthorizationType
from amelie.tools.logic import current_academic_year_with_holidays, current_association_year
from amelie.tools.validators import CheckDigitValidator
from amelie.tools.widgets import DateSelector, MemberSelect
from amelie.tools.encodings import normalize_to_ascii


class PersonalDetailsEditForm(forms.ModelForm):
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect, label=_l('Gender'))
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect, label=_l('Language of preference'))
    international_member = forms.ChoiceField(choices=Person.InternationalChoices.choices, widget=widgets.RadioSelect,
                                             label=_l("International student"))
    date_of_birth = forms.DateField(widget=DateSelector, label=_l('Birth date'))
    preferences = forms.ModelMultipleChoiceField(Preference.objects.filter(adjustable=True), required=False,
                                                 widget=widgets.CheckboxSelectMultiple, label=_l('Preferences'))

    def save(self, *args, **kwargs):
        if self.has_changed():
            changes = []
            old_person = Person.objects.get(id=self.instance.id)
            for field in self.changed_data:
                if field == "preferences":
                    old = [preference.name for preference in getattr(old_person, field).all()]
                    new = [preference.name for preference in self.cleaned_data[field].all()] + [preference.name for preference in self.instance.preferences.filter(adjustable=False)]

                    added = list(set(new)-set(old))
                    removed = list(set(old)-set(new))

                    changes.append({
                        'field': 'Preferences',
                        'added': '  + ' + '\n  + '.join(added) if added else '',
                        'removed': '  - ' + '\n  - '.join(removed) if removed else ''
                    })
                else:
                    changes.append({
                        'field': field,
                        'old': getattr(old_person, field),
                        'new': self.cleaned_data[field]
                    })

            task = MailTask(template_name='members/profile_changed.mail',
                            report_to=settings.EMAIL_REPORT_TO,
                            report_always=False,
                            priority=TaskPriority.MEDIUM)

            context = {'obj': str(self.instance),
                       'url': self.instance.get_absolute_url(),
                       'changes': changes,
                       }

            tos = ['Secretary Inter-Actief <secretary@inter-actief.net>']

            task.add_recipient(Recipient(tos=tos, context=context))

            task.send()

        # Get preferences for non-adjustable preferences to insert them into the form so we don't lose them.
        preferences = list(self.instance.preferences.filter(adjustable=False))

        person = super(PersonalDetailsEditForm, self).save()

        for preference in preferences:
            person.preferences.add(preference)

        return person

    class Meta:
        model = Person
        fields = ('gender', 'date_of_birth', 'preferred_language', 'address', 'postal_code', 'city', 'country',
                  'address_parents', 'postal_code_parents', 'city_parents', 'country_parents', 'email_address_parents',
                  'can_use_parents_address', 'telephone', 'email_address', 'preferences',
                  'shell', 'international_member')


class PersonalStudyEditForm(forms.Form):
    master = forms.ModelChoiceField(Study.objects.filter(primary_study=True, type=Study.StudyTypes.MSC, active=True),
                                    required=False)
    finished = forms.DateField(widget=DateSelector, initial=None, required=False, label=_l('Bachelor degree'))
    started = forms.DateField(widget=DateSelector, initial=None, label=_l('Started mastereducation'), required=False)

    def clean(self):
        if 'master' in self.cleaned_data and self.cleaned_data['master'] and (
                        'started' not in self.cleaned_data or not self.cleaned_data['started']):
            raise forms.ValidationError(_l('Please fill in a start date when filling in a mastercourse.'))
        return self.cleaned_data

    def save(self, study_period):
        if self.cleaned_data['finished']:
            study_period.end = self.cleaned_data['finished']
            study_period.graduated = True
            study_period.save()

        if self.cleaned_data['master']:
            student = study_period.student
            new_sp = StudyPeriod(student=student, study=self.cleaned_data['master'],
                                 begin=self.cleaned_data['started'])
            new_sp.save()


class PersonDataForm(forms.ModelForm):
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect)
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect)
    international_member = forms.ChoiceField(choices=Person.InternationalChoices.choices, widget=widgets.RadioSelect)

    class Meta:
        model = Person
        fields = ('first_name', 'last_name_prefix', 'last_name', 'initials', 'picture',
                  'gender', 'preferred_language', 'date_of_birth', 'international_member',
                  'address', 'postal_code', 'city', 'country', 'telephone', 'email_address', 'address_parents',
                  'postal_code_parents', 'city_parents', 'country_parents', 'email_address_parents',
                  'notes', 'account_name', 'nda', 'webmaster',
                  )

    def __init__(self, *args, instance=None, **kwargs):
        super(PersonDataForm, self).__init__(*args, instance=instance, **kwargs)
        if instance is not None:
            if instance.account_name:
                self.fields['account_name'].disabled = True
            else:
                account_name_suggestion = re.sub(r'[^\w\s]', '', normalize_to_ascii(f"{instance.last_name_prefix}{instance.last_name}{instance.initials}")).lower()
                self.fields['account_name'].help_text = " ".join([_("Suggestion:"), account_name_suggestion])


class ProfilePictureUploadForm(forms.Form):
    profile_picture = forms.ImageField(required=True)


class ProfilePictureVerificationForm(forms.Form):
    is_verified = forms.BooleanField(initial=False, required=False, label=_l('Verify'))
    id = forms.IntegerField(widget=forms.HiddenInput())


class PersonPreferencesForm(forms.ModelForm):
    preferences = forms.ModelMultipleChoiceField(Preference.objects.all(), required=False,
                                                 widget=widgets.CheckboxSelectMultiple)

    def __init__(self, preferences_set=None, *args, **kwargs):
        super(PersonPreferencesForm, self).__init__(*args, **kwargs)

        if preferences_set is not None:
            self.fields['preferences'].queryset = preferences_set

    def save(self, commit=True):
        """
        Saves this ``form``'s cleaned_data into model instance ``self.instance``.

        If commit=True, then the changes to ``instance`` will be saved to the database. Returns ``instance``.
        """
        if self.errors:
            raise ValueError("The Person could not be saved because the data didn't validate.")

        # Wrap up the saving of m2m data as a function.
        def save_m2m():
            cleaned_data = self.cleaned_data

            current = self.instance.preferences.all()
            should = cleaned_data['preferences']

            def _remove(preference):
                return preference not in should

            def _add(preference):
                return preference not in current

            add = filter(_add, should)
            remove = filter(_remove, current)

            self.instance.preferences.add(*add)
            self.instance.preferences.remove(*remove)

        if commit:
            # If we are committing, save the m2m data immediately.
            save_m2m()
        else:
            # We're not committing. Add a method to the form to allow deferred
            # saving of m2m data.
            self.save_m2m = save_m2m
        return self.instance

    class Meta:
        model = Person
        fields = ('preferences',)


class EmployeeForm(forms.ModelForm):
    departments = forms.ModelMultipleChoiceField(Department.objects.all(), required=False,
                                                 widget=widgets.CheckboxSelectMultiple, label=_l('Related to'))

    class Meta:
        model = Employee
        fields = ("number", "end",)


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ("number",)


class PersonStudyForm(forms.ModelForm):
    study = forms.ModelMultipleChoiceField(Study.objects.filter(active=True), widget=widgets.RadioSelect)

    class Meta:
        model = StudyPeriod
        fields = ("study", "begin", "dogroup",)


class PersonPaymentForm(forms.Form):
    date = forms.DateField(initial=datetime.date.today())
    method = forms.ModelChoiceField(PaymentType.objects.all())


class MembershipForm(forms.ModelForm):
    year = forms.IntegerField(initial=current_association_year, widget=widgets.RadioSelect())
    type = forms.ModelChoiceField(MembershipType.objects.filter(active=True), label=_l('Type'))

    class Meta:
        model = Membership
        fields = ('year', 'type',)

    def __init__(self, *args, **kwargs):
        super(MembershipForm, self).__init__(*args, **kwargs)
        self.fields['year'].widget.choices = ((current_association_year(), _l('Current association year')),
                                              (current_association_year() + 1, _l('Upcoming association year')),)


class MembershipEndForm(forms.ModelForm):
    ended = forms.DateField(widget=widgets.RadioSelect)

    class Meta:
        model = Membership
        fields = ("ended",)

    def __init__(self, *args, **kwargs):
        super(MembershipEndForm, self).__init__(*args, **kwargs)
        self.fields['ended'].widget.choices = ((date.today(), _l('Immediately')),
                                               (date(current_association_year() + 1, 7, 1),
                                                _l('At the end of the association year')),)


class MandateForm(forms.ModelForm):
    authorization_type = forms.ModelChoiceField(queryset=AuthorizationType.objects.filter(active=True))

    class Meta:
        model = Authorization
        fields = ('authorization_type', 'iban', 'bic', 'account_holder_name', 'start_date')
        labels = {"bic": "BIC*"}

    def __init__(self, *args, **kwargs):
        super(MandateForm, self).__init__(*args, **kwargs)
        self.fields['iban'].required = True
        self.fields['account_holder_name'].required = True

    def clean(self):
        cleaned_data = super(MandateForm, self).clean()
        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if not cleaned_data['bic']:
            if not cleaned_data['iban'][:2] == 'NL':
                raise forms.ValidationError(_l('BIC has to be entered for foreign bankaccounts.'))
            elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
            else:
                raise forms.ValidationError(_l('BIC could not be generated, please enter yourself.'))
        return cleaned_data


class MandateEndForm(forms.ModelForm):
    class Meta:
        model = Authorization
        fields = ('end_date',)

    def __init__(self, *args, **kwargs):
        super(MandateEndForm, self).__init__(*args, **kwargs)
        self.fields['end_date'].required = True


class PersonSearchForm(forms.Form):
    person = forms.IntegerField(widget=MemberSelect(attrs={'autofocus': 'autofocus'}), label=_l('Person'),
                                error_messages={'required': _l('Choose a name from the suggestions.')})


class SearchForm(forms.Form):
    search = forms.CharField(max_length=40, label=_l('Search'),
                             widget=widgets.TextInput(attrs={'accesskey': 'f', 'autofocus': 'autofocus', }))


def _initial_preferences():
    return [x.pk for x in Preference.objects.filter(default=True).exclude(first_time=False)]


class PersonCreateForm(forms.ModelForm):
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect)
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect)
    international_member = forms.ChoiceField(choices=Person.InternationalChoices.choices, widget=widgets.RadioSelect)

    student_number = forms.IntegerField(required=False, validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])
    study = forms.ModelMultipleChoiceField(Study.objects.filter(active=True), widget=widgets.CheckboxSelectMultiple, required=False)
    generation = forms.IntegerField(required=False)

    membership = forms.ModelChoiceField(MembershipType.objects.filter(
        Q(name_nl='Secundair jaarlid') | Q(name_nl='Primair jaarlid') |
        Q(name_nl='Studielang (eerste jaar)') | Q(name_nl='Medewerker jaar')
    ), required=True, empty_label=None, widget=widgets.RadioSelect)

    iban = IBANFormField(label=_l('IBAN'), required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    bic = BICFormField(label=_l('BIC'), required=False)
    mandate_contribution = forms.BooleanField(required=False)
    mandate_other = forms.BooleanField(required=False)

    done = forms.BooleanField(required=True)

    # Here you can also disable specific preferences.
    # If these should be enabled by default, that needs to be done at 'def save()'
    preferences = forms.ModelMultipleChoiceField(Preference.objects.exclude(first_time=False),
                                                 initial=_initial_preferences,
                                                 widget=widgets.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Person
        fields = (
            'first_name', 'last_name_prefix', 'last_name', 'initials', 'gender', 'date_of_birth', 'address',
            'postal_code', 'city', 'country', 'email_address', 'telephone',
            'preferred_language', 'preferences', 'international_member')
        widgets = {'preferred_language': widgets.RadioSelect(), 'date_of_birth': DateSelector}

    def clean(self):
        cleaned_data = super(PersonCreateForm, self).clean()

        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if cleaned_data['study']:
            # Generation is mandatory if study is chosen
            if 'generation' not in cleaned_data or not cleaned_data['generation']:
                raise forms.ValidationError(
                    _l("A study has been chosen, but no cohort was specified. Enter the missing data to continue.")
                )

        if cleaned_data['mandate_contribution'] or cleaned_data['mandate_other']:
            if not cleaned_data['iban']:
                raise forms.ValidationError(_l('IBAN is required if a mandate is checked!'))
            if not cleaned_data['bic']:
                if not cleaned_data['iban'][:2] == 'NL':
                    raise forms.ValidationError(_l('BIC has to be entered for foreign bankaccounts.'))
                elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                    cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
                else:
                    raise forms.ValidationError(_l('BIC could not be generated, please enter yourself.'))

        return cleaned_data

    def clean_student_number(self):
        if self.cleaned_data['student_number'] and Student.objects.filter(
                number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("A student with this student number already exists."))
        if self.cleaned_data['student_number'] and UnverifiedEnrollment.objects.filter(
            student_number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("This student number is already pre-enrolled. A board member can activate your account."))
        return self.cleaned_data['student_number']

    def save(self, *args, **kwargs):
        person = super(PersonCreateForm, self).save(*args, **kwargs)
        for preference in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(preference)
        return person


class RegistrationForm(forms.ModelForm):
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect)
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect)
    international_member = forms.ChoiceField(choices=Person.InternationalChoices.choices, widget=widgets.RadioSelect)

    student_number = forms.IntegerField(validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])
    study = forms.ModelMultipleChoiceField(Study.objects.filter(primary_study=True, active=True),
                                           widget=widgets.CheckboxSelectMultiple)
    # Queryset will be set dynamically in __init__
    dogroup = forms.ModelChoiceField(DogroupGeneration.objects.none(), widget=widgets.RadioSelect, required=False)

    membership = forms.ModelChoiceField(MembershipType.objects.filter(
            Q(name_nl='Primair jaarlid') | Q(name_nl='Studielang (eerste jaar)')
    ), required=True, empty_label=None, widget=widgets.RadioSelect)

    iban = IBANFormField(label=_l('IBAN'), required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    bic = BICFormField(label=_l('BIC'), required=False)
    mandate_contribution = forms.BooleanField(required=False)
    mandate_other = forms.BooleanField(required=False)

    picture = forms.ImageField(required=False)

    done = forms.BooleanField(required=True)

    # Here you can also disable specific preferences.
    # If these should be enabled by default, that needs to be done at 'def save()'
    preferences = forms.ModelMultipleChoiceField(Preference.objects.exclude(first_time=False),
                                                 initial=_initial_preferences,
                                                 widget=widgets.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Person
        fields = (
            'first_name', 'last_name_prefix', 'last_name', 'initials', 'gender', 'date_of_birth', 'address',
            'postal_code', 'city', 'country', 'email_address', 'telephone', 'preferred_language', 'preferences',
            'picture', 'international_member', 'address_parents', 'postal_code_parents', 'city_parents',
            'country_parents', 'email_address_parents', 'can_use_parents_address')
        widgets = {'preferred_language': widgets.RadioSelect(), 'date_of_birth': DateSelector}

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.fields['dogroup'].queryset = DogroupGeneration.objects.filter(generation=current_academic_year_with_holidays())

    def clean(self):
        cleaned_data = super(RegistrationForm, self).clean()

        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if cleaned_data['mandate_contribution'] or cleaned_data['mandate_other']:
            if not cleaned_data['iban']:
                raise forms.ValidationError(_l('IBAN is required if a mandate is checked!'))
            if not cleaned_data['bic']:
                if not cleaned_data['iban'][:2] == 'NL':
                    raise forms.ValidationError(_l('BIC has to be entered for foreign bankaccounts.'))
                elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                    cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
                else:
                    raise forms.ValidationError(_l('BIC could not be generated, please enter yourself.'))

        return cleaned_data

    def clean_student_number(self):
        if Student.objects.filter(number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("A student with this student number already exists."))
        if UnverifiedEnrollment.objects.filter(student_number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("This student number is already pre-enrolled. A board member can activate your account."))
        return self.cleaned_data['student_number']

    def save(self, *args, **kwargs):
        person = super(RegistrationForm, self).save(*args, **kwargs)
        for preference in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(preference)

        return person


class RegistrationFormPersonalDetails(forms.ModelForm):
    date_of_birth = forms.DateField(required=True, widget=DateSelector)
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect)
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect)
    international_member = forms.ChoiceField(choices=Person.InternationalChoices.choices, widget=widgets.RadioSelect)

    class Meta:
        model = Person
        fields = ('first_name', 'last_name_prefix', 'last_name', 'initials', 'date_of_birth', 'gender',
                  'email_address', 'preferred_language', 'international_member')


class RegistrationFormPersonalDetailsEmployee(forms.ModelForm):
    date_of_birth = forms.DateField(required=True, widget=DateSelector)
    gender = forms.ChoiceField(choices=Person.GenderTypes.choices, widget=widgets.RadioSelect)
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, widget=widgets.RadioSelect)

    class Meta:
        model = Person
        fields = ('first_name', 'last_name_prefix', 'last_name', 'initials', 'date_of_birth', 'gender',
                  'email_address', 'preferred_language')


class RegistrationFormStepMemberContactDetails(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('address', 'postal_code', 'city', 'country', 'telephone')


class RegistrationFormStepParentsContactDetails(forms.ModelForm):
    # Country has a default value, clear that
    country_parents = forms.CharField(max_length=25, required=False)

    class Meta:
        model = Person
        fields = ('can_use_parents_address', 'email_address_parents', 'address_parents', 'postal_code_parents',
                  'city_parents', 'country_parents')

    def clean(self):
        cleaned_data = super(RegistrationFormStepParentsContactDetails, self).clean()
        can_use_data = cleaned_data.get("can_use_parents_address")
        email_address = cleaned_data.get("email_address_parents")
        address = cleaned_data.get("address_parents")
        postal_code = cleaned_data.get("postal_code_parents")
        city = cleaned_data.get("city_parents")
        country = cleaned_data.get("country_parents")

        # If we can use the data, but no (basic) data is given, error out.
        if can_use_data and not email_address:
            raise forms.ValidationError(_l("If we can use your parent(s)/guardian(s) data, "
                                          "then you need to enter at least their e-mail address!"))

        # If we cannot use the data, but data is given, error out.
        if not can_use_data and any([address, postal_code, city, country, email_address]):
            raise forms.ValidationError(_l("If we can not use your parent(s)/guardian(s) data, "
                                          "then you do not need to enter any data!"))

        return cleaned_data


class RegistrationFormStepGeneralStudyDetails(forms.Form):
    student_number = forms.IntegerField(validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])
    study = forms.ModelMultipleChoiceField(Study.objects.filter(active=True), widget=widgets.CheckboxSelectMultiple, required=False)
    generation = forms.IntegerField(
        required=False,
        min_value=1981,
        max_value=date.today().year + 2,
        initial=date.today().year,
    )

    def clean(self):
        cleaned_data = super(RegistrationFormStepGeneralStudyDetails, self).clean()

        # Generation is mandatory if study is chosen
        if ('generation' not in cleaned_data.keys() or not cleaned_data['generation']) and \
                ('study' in cleaned_data.keys() and cleaned_data['study']):
            raise forms.ValidationError(
                _l("A study has been chosen, but no cohort was specified. Enter the missing data to continue.")
            )

        # Study is mandatory if generation is chosen
        if ('study' not in cleaned_data.keys() or not cleaned_data['study']) and \
                ('generation' in cleaned_data.keys() and cleaned_data['generation']):
            raise forms.ValidationError(
                _l("A cohort has been chosen, but no study was specified. Enter at least one study to continue.")
            )

        return cleaned_data

    def clean_student_number(self):
        if Student.objects.filter(number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("A student with this student number already exists."))
        if UnverifiedEnrollment.objects.filter(student_number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("This student number is already pre-enrolled. A board member can activate your account."))
        return self.cleaned_data['student_number']


class RegistrationFormStepFreshmenStudyDetails(forms.Form):
    study = forms.ModelMultipleChoiceField(Study.objects.filter(primary_study=True, active=True))
    student_number = forms.IntegerField(validators=[CheckDigitValidator(7), MaxValueValidator(9999999)])
    # Queryset will be set dynamically in __init__
    dogroup = forms.ModelChoiceField(DogroupGeneration.objects.none(), widget=widgets.RadioSelect, required=False)

    def __init__(self, *args, **kwargs):
        super(RegistrationFormStepFreshmenStudyDetails, self).__init__(*args, **kwargs)
        self.fields['dogroup'].queryset = DogroupGeneration.objects.filter(generation=current_academic_year_with_holidays())

    def clean_student_number(self):
        if Student.objects.filter(number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("A student with this student number already exists."))
        if UnverifiedEnrollment.objects.filter(student_number=self.cleaned_data['student_number']).exists():
            raise forms.ValidationError(_l("This student number is already pre-enrolled. A board member can activate your account."))
        return self.cleaned_data['student_number']


class RegistrationFormStepEmployeeDetails(forms.Form):
    employee_number = forms.IntegerField(validators=[MinValueValidator(7640000), MaxValueValidator(9999999)])

    def clean_employee_number(self):
        if Employee.objects.filter(number=self.cleaned_data['employee_number']).exists():
            raise forms.ValidationError(_l("An employee with this employee number already exists."))
        return self.cleaned_data['employee_number']


class RegistrationFormStepGeneralMembershipDetails(forms.Form):
    membership = forms.ModelChoiceField(MembershipType.objects.filter(
        Q(name_en='Secondary yearlong') | Q(name_en='Primary yearlong') | Q(name_en='Studylong (first year)')
    ), required=True, empty_label=None, widget=widgets.RadioSelect)


class RegistrationFormStepEmployeeMembershipDetails(forms.Form):
    membership = forms.ModelChoiceField(MembershipType.objects.filter(
        Q(name_en='Employee yearlong')
    ), required=True, empty_label=None, widget=widgets.RadioSelect)


class RegistrationFormStepFreshmenMembershipDetails(forms.Form):
    membership = forms.ModelChoiceField(MembershipType.objects.filter(
            Q(name_en='Primary yearlong') | Q(name_en='Studylong (first year)')
    ), required=True, empty_label=None, widget=widgets.RadioSelect)


class RegistrationFormStepAuthorizationDetails(forms.Form):
    authorization_contribution = forms.BooleanField(required=False)
    authorization_other = forms.BooleanField(required=False)
    iban = IBANFormField(label=_l('IBAN'), required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    bic = BICFormField(label=_l('BIC'), required=False)

    def clean_iban(self):
        if str(self.cleaned_data['iban']).strip() == "NL18ABNA0484869868":
            raise forms.ValidationError(_l("Please enter your own bank account number!"))
        return self.cleaned_data['iban']

    def clean_bic(self):
        bic = str(self.cleaned_data['bic']).strip()
        if bic == "":
            return self.cleaned_data['bic']

        if not settings.DEBUG:
            if bic in settings.COOKIE_CORNER_BANK_CODES.values():
                return self.cleaned_data['bic']
            # handle if does not exist, throw error showing the command to run
            try:
                # csv file can be updated with `python manage.py update_bic_csv`
                with open(os.path.join(settings.MEDIA_ROOT, 'data/bic_list.csv'), 'r', encoding="utf_8") as csv_file:
                    csv_reader = csv.reader(csv_file, delimiter=',')
                    next(csv_reader)  # skip the header
                    for row in csv_reader:
                        # only check the first 8 characters, last 3 are for the branch code
                        if bic[:8] == row[4][:8]:
                            return self.cleaned_data['bic']
            except IOError as e:
                raise IOError(u"Reading file at {} failed (run 'manage.py update_bic_csv' to create it if it does not exist) {}"
                              .format(os.path.join(settings.MEDIA_ROOT, 'bic_list.csv'), e))

            raise forms.ValidationError(_l("BIC is not from a SEPA country"))

    def clean(self):
        cleaned_data = super(RegistrationFormStepAuthorizationDetails, self).clean()

        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if cleaned_data['authorization_contribution'] or cleaned_data['authorization_other']:
            if not cleaned_data['iban']:
                raise forms.ValidationError(_l('IBAN is required if a mandate is checked!'))
            if not cleaned_data['bic']:
                if not cleaned_data['iban'][:2] == 'NL':
                    raise forms.ValidationError(_l('BIC has to be entered for foreign bankaccounts.'))
                elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                    cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
                else:
                    raise forms.ValidationError(_l('BIC could not be generated, please enter yourself.'))

        return cleaned_data


class RegistrationFormStepPersonalPreferences(forms.ModelForm):
    # Here you can also disable specific preferences.
    # If these should be enabled by default, that needs to be done at 'def save()'
    preferences = forms.ModelMultipleChoiceField(Preference.objects.exclude(first_time=False),
                                                 initial=_initial_preferences,
                                                 widget=widgets.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Person
        fields = ('preferences', )

    def save(self, *args, **kwargs):
        person = super(RegistrationFormStepPersonalPreferences, self).save(*args, **kwargs)
        for preference in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(preference)

        return person


class RegistrationFormStepFinalCheck(forms.Form):
    done = forms.BooleanField(required=True)
    over_16_or_permission_and_agree_to_privacy_statement = forms.BooleanField(required=True)


class PreRegistrationPrintAllForm(forms.Form):
    class SortOptions(TextChoices):
        LAST_NAME = 'last_name', _l('By last name')
        FIRST_NAME = 'first_name', _l('By first name')
        STUDENT_NUMBER = 'student_number', _l('By student number')
        ID = 'id', _l('By order of pre-enrollment')

    sort_by = forms.ChoiceField(choices=SortOptions.choices, required=True, initial=SortOptions.LAST_NAME)
    group_by_dogroup = forms.BooleanField(required=False, label="Group forms by do-group?", initial=True)
    signing_date = forms.DateField(required=True, widget=DateSelector, initial=datetime.date.today())
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES, required=True, initial="en")


class FunctionForm(forms.ModelForm):
    committee = forms.ModelChoiceField(queryset=Committee.objects.non_parent_committees())
    function = forms.CharField(max_length=75, label=_l('Position'))

    class Meta:
        model = Function
        fields = ["committee", "function", 'begin', "end"]
        widgets = {
            'begin': DateSelector,
            "end": DateSelector,
        }

    def clean_function(self):
        value = self.cleaned_data.get('function', None)
        if self.instance.pk:
            diff = SequenceMatcher(None, self.instance.function, value)
            # if diff.ratio() < 0.9:
            #    raise forms.ValidationError, _("You can't just edit the function, "
            #                                   "end this function and create a new one within the association")
        return value


class CommitteeMemberForm(forms.ModelForm):
    class Meta:
        model = Function
        fields = ["person", "function", 'begin', "end"]
        widgets = {
            "person": MemberSelect,
            'begin': DateSelector,
            "end": DateSelector,
        }


class CommitteeForm(forms.ModelForm):
    abbreviation = forms.RegexField(regex="[A-Za-z0-9]+", max_length=20)
    category = forms.ModelChoiceField(CommitteeCategory.objects.all(), widget=forms.Select, required=False,
                                      label=_l('Category'))
    parent_committees = forms.ModelMultipleChoiceField(Committee.objects.active(), widget=forms.SelectMultiple,
                                                       label=_l('Parent committee'), required=False)

    class Meta:
        model = Committee
        fields = ["name", "abbreviation", "information_nl", "information_en", 'logo', "group_picture", "category",
                  "parent_committees", 'email', 'website', "ledger_account_number", 'private_email', 'gitlab',
                  'superuser', "abolished"]
        widgets = {
            "abolished": DateSelector,
        }


class SaveNewFirstModelFormSet(BaseInlineFormSet):
    def save(self, *args, **kwargs):
        """Override save with inverted order of saving. Commit is always True here."""
        return self.save_new_objects(commit=True) + self.save_existing_objects(commit=True)


class StudentNumberForm(forms.Form):
    student_number = forms.IntegerField(label=_l('Student number'))

    def clean_student_number(self):
        if not Student.objects.filter(number=self.cleaned_data["student_number"]).exists():
            raise forms.ValidationError(_l("There is no student with this student number."))
        return self.cleaned_data["student_number"]


inject_style(SearchForm, CommitteeForm, PersonalDetailsEditForm, PersonalStudyEditForm, PersonDataForm, ProfilePictureVerificationForm, ProfilePictureUploadForm)

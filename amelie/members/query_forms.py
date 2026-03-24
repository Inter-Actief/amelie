import datetime
import unicodedata
from datetime import date

import re
from django import forms
from django.core.validators import MaxLengthValidator
from django.db.models import Q
from django.forms import widgets
from django.template import Template
from django.utils import translation
from django.utils.translation import gettext_lazy as _l
from functools import reduce

from amelie.api.models import PushNotification
from amelie.tools.const import TaskPriority
from amelie.iamailer.mailer import render_mail
from amelie.iamailer.mailtask import MailTask
from amelie.style.forms import inject_style
from amelie.members.models import Study, Person, Preference, MembershipType, \
    Committee, Department, DogroupGeneration, LANGUAGE_CHOICES, Membership
from amelie.personal_tab.models import AuthorizationType
from amelie.tools.logic import current_academic_year_strict, current_association_year
from amelie.tools.mail import PersonRecipient, person_dict


def _find_years():
    year = current_association_year()
    return [(x, x) for x in range(year - 9, year + 1)]


class QueryForm(forms.Form):
    name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))
    id = forms.IntegerField(required=False, label=_l('Amélie-number'))
    sm_number = forms.CharField(max_length=10, required=False, label=_l('S/M number'))
    phone_number = forms.CharField(max_length=20, required=False, label=_l('Phonenumber'))
    email_address = forms.CharField(max_length=100, required=False, label=_l('E-mail address'))
    gender = forms.MultipleChoiceField(required=False, choices=Person.GenderTypes.choices,
                                       widget=widgets.CheckboxSelectMultiple)
    minor = forms.BooleanField(required=False, label=_l('Younger than 18 years old'))

    member = forms.BooleanField(required=False, label=_l('Return former members'))
    old_member = forms.BooleanField(required=False, label=_l('Only return former members'))
    paid = forms.BooleanField(required=False, label=_l('Has not paid yet'))
    member_in_year = forms.MultipleChoiceField(required=False, label=_l('Was a member in one of these years'))

    study = forms.ModelChoiceField(Study.objects.all(), required=False)
    studies = forms.CharField(max_length=200, required=False)
    primary_studies = forms.BooleanField(required=False)
    study_year = forms.MultipleChoiceField(choices=(), required=False)

    international_member = forms.MultipleChoiceField(choices=Person.InternationalChoices.choices, required=False,
                                                     widget=widgets.CheckboxSelectMultiple)

    preference_not = forms.BooleanField(required=False,
                                        label=_l('Return members who do not have the following options'))
    preference = forms.ModelMultipleChoiceField(Preference.objects.all(), required=False,
                                                widget=widgets.CheckboxSelectMultiple)

    membership = forms.ModelMultipleChoiceField(MembershipType.objects.all(), required=False)
    not_verified_membership = forms.BooleanField(required=False, label=_l("Membership is not verified"))
    verified_membership = forms.BooleanField(required=False, label=_l("Membership is verified (or not needed for type)"))

    active = forms.BooleanField(required=False, label=_l('Is an active member'))
    not_active = forms.BooleanField(required=False, label=_l('Is a not-active member'))
    has_nda = forms.BooleanField(required=False, label=_l('Has signed an NDA'))
    committee = forms.ModelChoiceField(Committee.objects.all(), required=False, label=_l('Once did'))
    committee_now = forms.ModelChoiceField(Committee.objects.filter(abolished__isnull=True), required=False,
                                           label=_l('Does'))
    active_year = forms.MultipleChoiceField(choices=(), required=False, label=_l('Was active in'))

    employee = forms.BooleanField(required=False, label=_l('Member is employee'))
    department = forms.ModelMultipleChoiceField(Department.objects.all(), required=False, label=_l('Belongs to'))

    has_dogroup = forms.BooleanField(required=False, label=_l('Has a dogroup'))
    has_no_dogroup = forms.BooleanField(required=False, label=_l('Has no dogroup'))
    dogroup = forms.ModelMultipleChoiceField(DogroupGeneration.objects.all(), required=False)

    preferred_language = forms.MultipleChoiceField(choices=LANGUAGE_CHOICES, required=False)

    # Mandate
    mandates = forms.ModelMultipleChoiceField(
        AuthorizationType.objects.all(), required=False, label=_l('Mandate'))
    mandate = forms.IntegerField(required=False, label=_l('Mandate number'))
    iban = forms.CharField(max_length=34, required=False, label=_l('IBAN'))

    # Here are the pre-programmed queries
    # Second/Third/Fourth/Fifth years and older
    second_year_and_older = forms.BooleanField(required=False, label=_l(
        'Students in their second year or higher, including all masters (primary studies)'))
    third_year_and_older = forms.BooleanField(required=False, label=_l(
        'Students in their third year or higher, including all masters (primary studies)'))
    fourth_year_and_older = forms.BooleanField(required=False, label=_l(
        'Students in their fourth year or higher, including all masters (primary studies)'))
    fifth_year_and_older = forms.BooleanField(required=False, label=_l(
        'Students in their fifth year or higher, including all masters (primary studies)'))

    def __init__(self, *args, **kwargs):
        super(QueryForm, self).__init__(*args, **kwargs)
        self.fields['study_year'].choices = _find_years()
        self.fields['active_year'].choices = _find_years()
        self.fields['member_in_year'].choices = _find_years()

    def clean(self):
        cleaned_data = super(QueryForm, self).clean()

        if cleaned_data.get('sm_number'):
            try:
                re.compile(cleaned_data['sm_number'])
            except:
                raise forms.ValidationError(_l("Invalid student or employee number."))

        if cleaned_data.get('iban'):
            try:
                re.compile(cleaned_data['iban'])
            except:
                raise forms.ValidationError(_l("Invalid IBAN."))

        if cleaned_data.get('name'):
            try:
                re.compile(cleaned_data['name'])
            except:
                raise forms.ValidationError(_l("Invalid characters in name."))

        return cleaned_data

    def filter(self, persons):
        cleaned_data = self.clean()

        bsc_primary_studies = Study.objects.filter(primary_study=True, type=Study.StudyTypes.BSC)
        msc_primary_studies = Study.objects.filter(primary_study=True, type=Study.StudyTypes.MSC)

        # === Basic data ===
        if cleaned_data['name']:
            names = cleaned_data['name'].strip().split(' ')
            for name in names:
                # Skip empty substrings, iregex can't handle those (#424)
                if name:
                    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
                    persons = persons.filter(slug__iregex=name)

        if cleaned_data['id']:
            persons = persons.filter(id=cleaned_data['id'])

        if cleaned_data['sm_number']:
            try:
                number = re.sub("\D", "", cleaned_data['sm_number'])
                number = int(number)
                persons = persons.filter(Q(student__number__iregex=number) | Q(employee__number__iregex=number))
            except ValueError:
                pass

        if cleaned_data['phone_number']:
            number = cleaned_data['phone_number']
            persons = persons.filter(telephone__iregex=number)

        if cleaned_data['email_address']:
            email_address = cleaned_data['email_address']
            persons = persons.filter(email_address__iregex=email_address)

        if cleaned_data['gender']:
            persons = persons.filter(gender__in=cleaned_data['gender'])

        if cleaned_data['minor']:
            persons = persons.filter(date_of_birth__gte=date.today() - datetime.timedelta(days=6570))

        # === Membership ===
        memberships = Membership.objects.all()

        if not cleaned_data['member']:
            if cleaned_data['member_in_year']:
                qs = reduce(lambda a, b: a | b, [
                    Q(year=y) for y in cleaned_data['member_in_year']
                ])

                memberships = memberships.filter(qs)
            elif not cleaned_data['old_member']:
                # Query only current members if it is not specified that (only) old members should be returned.
                memberships = memberships.filter(Q(ended__gt=date.today()) | Q(ended__isnull=True),
                                                 year=current_association_year())
        elif cleaned_data['member_in_year']:

            qs = reduce(lambda a, b: a | b, [
                Q(year=y) for y in cleaned_data['member_in_year']
            ])
            memberships = memberships.filter(qs)

        if cleaned_data['old_member']:
            # Explicitly exclude persons with membership in current year. Only excluding the current membership from the
            # queried memberships is insufficient, as current members might still match with their former memberships.
            persons = persons.exclude(membership__in=Membership.objects.filter(
                Q(ended__gt=date.today()) | Q(ended__isnull=True), year=current_association_year()))

        if cleaned_data['paid']:
            memberships = memberships.filter(type__price__gt=0, payment__isnull=True)

        if cleaned_data['membership']:
            memberships = memberships.filter(type__in=cleaned_data['membership'])

        if cleaned_data['not_verified_membership']:
            memberships = memberships.filter(verified_on__isnull=True, type__needs_verification=True)
        if cleaned_data['verified_membership']:
            memberships = memberships.filter(Q(verified_on__isnull=False) | Q(type__needs_verification=False))

        persons = persons.filter(membership__in=memberships)

        # === Study ===
        if cleaned_data['study']:
            persons = persons.filter(
                student__studyperiod__study=cleaned_data['study'],
                student__studyperiod__end=None,
            )

        if cleaned_data['studies']:
            persons = persons.filter(
                student__studyperiod__study__abbreviation__in=[x.strip().upper() for x in
                                                               cleaned_data['studies'].split(',')],
                student__studyperiod__end=None,
            )

        if cleaned_data['primary_studies']:
            persons = persons.filter(
                student__studyperiod__study__primary_study=True,
                student__studyperiod__end=None,
            )

        if cleaned_data['study_year']:
            qs = reduce(lambda a, b: a | b, [
                Q(student__studyperiod__begin__year=year) for year in cleaned_data['study_year']
            ])
            persons = persons.filter(qs)

            if cleaned_data['studies']:
                qs = reduce(lambda a, b: a | b, [Q(
                    student__studyperiod__begin__year=year,
                    student__studyperiod__study__abbreviation__in=[x.strip().upper() for x in
                                                                   cleaned_data['studies'].split(',')]
                ) for year in cleaned_data['study_year']])
                persons = persons.filter(qs, student__studyperiod__end=None)

            if cleaned_data['primary_studies']:
                qs = reduce(lambda a, b: a | b, [Q(
                    student__studyperiod__begin__year=year,
                    student__studyperiod__study__primary_study=True
                ) for year in cleaned_data['study_year']])
                persons = persons.filter(qs, student__studyperiod__end=None)

            if cleaned_data['study']:
                qs = reduce(lambda a, b: a | b, [Q(
                    student__studyperiod__begin__year=year,
                    student__studyperiod__study=cleaned_data['study']
                ) for year in cleaned_data['study_year']])
                persons = persons.filter(qs, student__studyperiod__end=None)

        # === Employee ===
        if cleaned_data['employee']:
            persons = persons.filter(employee__pk__isnull=False, employee__end__isnull=True)

        if cleaned_data['department']:
            persons = persons.filter(employee__departments__in=cleaned_data['department'])

        # === Activism ===
        if cleaned_data['active']:
            persons = persons.filter(function__begin__isnull=False, function__end__isnull=True,
                                     function__committee__abolished__isnull=True)

        if cleaned_data['not_active']:
            persons = persons.exclude(function__begin__isnull=False, function__end__isnull=True,
                                      function__committee__abolished__isnull=True)

        if cleaned_data['has_nda']:
            persons = persons.filter(nda=True)

        if cleaned_data['committee']:
            persons = persons.filter(function__committee=self.cleaned_data["committee"])

        if cleaned_data['committee_now']:
            persons = persons.filter(function__committee=self.cleaned_data['committee_now'], function__end__isnull=True)

        if cleaned_data['active_year']:
            years = [int(j) for j in self.cleaned_data['active_year']]
            qs = []
            for year in years:
                # The year is from 1 september to 31 august the next year
                # Q1: everything which begins before 31 august and ends after 31 august of year+1
                # Q2: everything which begins before 31 august, ends before 31 august but ends after 1 september
                # Q3: everything which begins before 31 august, but not ended yet. In this case the committee should
                #                                               not be abolished, or ar least after 1 september.

                # Q1
                qs.append((
                    Q(function__begin__lte=date(year + 1, 8, 31), function__end__gte=date(year + 1, 8, 31))
                ))

                # Q2
                qs.append((
                    Q(function__begin__lte=date(year + 1, 8, 31),
                      function__end__lte=date(year + 1, 8, 31),
                      function__end__gte=date(year, 9, 1))
                ))

                # Q3
                qs.append((
                    Q(function__begin__lte=date(year + 1, 8, 31), function__end__isnull=True) &
                    (
                        Q(function__committee__abolished__isnull=True) |
                        Q(function__committee__abolished__gte=date(year, 9, 1))
                    )
                ))
            persons = persons.filter(reduce(lambda x, y: x | y, qs))

        # === Do group ===
        if cleaned_data['dogroup']:
            persons = persons.filter(student__studyperiod__dogroup__in=cleaned_data['dogroup'])

        if cleaned_data['has_dogroup']:
            persons = persons.filter(student__studyperiod__dogroup__isnull=False)

        if cleaned_data['has_no_dogroup']:
            persons = persons.exclude(student__studyperiod__dogroup__isnull=False)

        # === Mandate ===
        if cleaned_data['mandates']:
            persons = persons.filter(authorization__authorization_type__in=cleaned_data['mandates'],
                                     authorization__is_signed=True, authorization__end_date__isnull=True)

        if cleaned_data['mandate']:
            persons = persons.filter(authorization__id=cleaned_data['mandate'])

        if cleaned_data['iban']:
            try:
                persons = persons.filter(authorization__iban__contains=cleaned_data['iban'])
            except ValueError:
                pass

        # === International Members ===
        if cleaned_data['international_member']:
            persons = persons.filter(international_member__in=cleaned_data['international_member'])

        if cleaned_data['preferred_language']:
            persons = persons.filter(preferred_language__in=cleaned_data['preferred_language'])

        # === Preferences ===
        if cleaned_data['preference']:
            if not cleaned_data['preference_not']:
                persons = persons.filter(preferences__in=cleaned_data['preference'])
            else:
                persons = persons.exclude(preferences__in=cleaned_data['preference'])

        # === Pre-programmed ===
        if cleaned_data['second_year_and_older']:
            q_date = date(current_academic_year_strict() - 1, 9, 1)
            persons = persons.filter(
                Q(student__studyperiod__study__in=bsc_primary_studies, student__studyperiod__begin__lte=q_date) |
                Q(student__studyperiod__study__in=msc_primary_studies)
            )

        if cleaned_data['third_year_and_older']:
            q_date = date(current_academic_year_strict() - 2, 9, 1)
            persons = persons.filter(
                Q(student__studyperiod__study__in=bsc_primary_studies, student__studyperiod__begin__lte=q_date) |
                Q(student__studyperiod__study__in=msc_primary_studies)
            )

        if cleaned_data['fourth_year_and_older']:
            q_date = date(current_academic_year_strict() - 3, 9, 1)
            persons = persons.filter(
                Q(student__studyperiod__study__in=bsc_primary_studies, student__studyperiod__begin__lte=q_date) |
                Q(student__studyperiod__study__in=msc_primary_studies)
            )

        if cleaned_data['fifth_year_and_older']:
            q_date = date(current_academic_year_strict() - 4, 9, 1)
            persons = persons.filter(
                Q(student__studyperiod__study__in=bsc_primary_studies, student__studyperiod__begin__lte=q_date) |
                Q(student__studyperiod__study__in=msc_primary_studies)
            )

        return persons.distinct()


class MailingForm(forms.Form):
    sender = forms.CharField(label=_l('Sender\'s name'), widget=widgets.Input(attrs={'size': 40}))
    email = forms.EmailField(label=_l('Sender\'s e-mail'), widget=widgets.EmailInput(attrs={'size': 50}))
    cc_email = forms.EmailField(required=False, label=_l('CC'), widget=widgets.EmailInput(attrs={'size': 50}))
    bcc_email = forms.EmailField(required=False, label=_l('BCC'), widget=widgets.EmailInput(attrs={'size': 50}))

    subject_nl = forms.CharField(widget=widgets.Input(attrs={'size': 100}))
    subject_en = forms.CharField(widget=widgets.Input(attrs={'size': 100}))

    template_nl = forms.CharField(widget=widgets.Textarea(attrs={'class': 'characters', 'rows': '20', 'cols': '90'}),
                                  label=_l('Message (Dutch)'))
    template_en = forms.CharField(widget=widgets.Textarea(attrs={'class': 'characters', 'rows': '20', 'cols': '90'}),
                                  label=_l('Message (English)'))

    def clean_subject(self):
        value = self.cleaned_data['subject']
        try:
            Template(value)
        except Exception:
            raise forms.ValidationError(_l("Invalid subject"))
        return value

    def clean_template(self):
        value = self.cleaned_data['template']
        try:
            Template(value)
        except Exception:
            raise forms.ValidationError(_l("Invalid template"))
        return value

    def build_template(self):
        template_string = '{% extends "members/mailing_base.mail" %}'
        template_string += '{% load i18n %}'

        template_string += '{% block subject %}'

        # This has to be scoped within this block, otherwise it breaks :O
        template_string += '{% get_current_language as LANG %}'
        template_string += '{% if LANG == \'en\' %}'
        template_string += self.cleaned_data['subject_en']
        template_string += '{% else %}'
        template_string += self.cleaned_data['subject_nl']
        template_string += '{% endif %}'
        template_string += '{% endblock %}'

        template_string += '{% block plain_content %}'
        # This has to be scoped within this block, otherwise it breaks :O
        template_string += '{% get_current_language as LANG %}'
        template_string += '{% if LANG == \"en\" %}'
        template_string += self.cleaned_data['template_en']
        template_string += '{% else %}'
        template_string += self.cleaned_data['template_nl']
        template_string += '{% endif %}'
        template_string += '{% endblock %}'

        return template_string

    def build_multilang_preview(self, person, context=None):
        template_string = self.build_template()
        if context is None:
            context = {}
        context['recipient'] = person_dict(person)

        old_lang = translation.get_language()

        try:
            previews = {}

            for lang in ['nl', 'en']:
                translation.activate(lang)
                preview_content, preview_subject, attachments = render_mail(Template(template_string), context)

                print(preview_content)

                previews[lang] = {
                    'content': preview_content,
                    'subject': preview_subject
                }

            return previews
        finally:
            translation.activate(old_lang)

    def build_task(self, recipients):
        """
        Build a MailTask based on this form for provided recipients.
        :param recipients: Either a list of Person objects or a list of tuples containing a Person object and a
                            context dict.
        :return: MailTask
        """

        template_string = self.build_template()
        sender = '"%s" <%s>' % (self.cleaned_data['sender'], self.cleaned_data['email'])
        ccs = [self.cleaned_data['cc_email']] if self.cleaned_data['cc_email'] else None
        bccs = [self.cleaned_data['bcc_email']] if self.cleaned_data['bcc_email'] else None

        task = MailTask(sender, template_string=template_string, report_to=sender, priority=TaskPriority.MEDIUM)

        for recipient in recipients:
            if isinstance(recipient, tuple):
                person, context = recipient
            else:
                person = recipient
                context = None

            if person.email_address:
                if not context:
                    context = {}

                task.add_recipient(PersonRecipient(person, ccs=ccs, bccs=bccs, context=context))

        return task

class ActivityMailingForm(MailingForm):
    include_waiting_list = forms.BooleanField(label=_l('Include people on the waiting list'), required=False)

class PushNotificationForm(forms.ModelForm):
    message_en = forms.CharField(widget=forms.Textarea(attrs={'class': 'characters'}), max_length=500)
    message_nl = forms.CharField(widget=forms.Textarea(attrs={'class': 'characters'}), max_length=500)

    class Meta:
        model = PushNotification
        fields = ('title_en', 'title_nl', 'message_en', 'message_nl')
        validators = {
            'title_en': [MaxLengthValidator(50)],
            'title_nl': [MaxLengthValidator(50)],
        }


inject_style(QueryForm, MailingForm)

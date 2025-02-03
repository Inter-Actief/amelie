import datetime
import time
import json
import re
import logging

from datetime import date
from decimal import Decimal
from functools import lru_cache
from io import BytesIO

from django.views import View
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError, BadRequest, ImproperlyConfigured
from django.db.models import Q, Sum, Max, F
from django.utils.dateparse import parse_date
from django.template.defaultfilters import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from fcm_django.models import FCMDevice
from formtools.wizard.views import SessionWizardView
from oauth2_provider.models import AccessToken, Grant

from wsgiref.util import FileWrapper

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.generic.edit import DeleteView, FormView

from amelie.claudia.models import Mapping, ExtraPerson
from amelie.members.forms import PersonDataForm, StudentNumberForm, \
    RegistrationFormPersonalDetails, RegistrationFormStepMemberContactDetails, \
    RegistrationFormStepParentsContactDetails, RegistrationFormStepFreshmenStudyDetails, \
    RegistrationFormStepGeneralMembershipDetails, RegistrationFormStepAuthorizationDetails, \
    RegistrationFormStepPersonalPreferences, RegistrationFormStepFinalCheck, RegistrationFormStepGeneralStudyDetails, \
    RegistrationFormStepFreshmenMembershipDetails, RegistrationFormStepEmployeeDetails, \
    RegistrationFormPersonalDetailsEmployee, RegistrationFormStepEmployeeMembershipDetails, PreRegistrationPrintAllForm
from amelie.members.models import Payment, PaymentType, Committee, Function, Membership, MembershipType, Employee, \
    Person, Student, Study, StudyPeriod, Preference, PreferenceCategory, UnverifiedEnrollment, Dogroup, \
    DogroupGeneration
from amelie.personal_tab.forms import RFIDCardForm
from amelie.personal_tab.models import Authorization, AuthorizationType, Transaction, SEPA_CHAR_VALIDATOR
from amelie.tools.auth import get_oauth_link_code, send_oauth_link_code_email, get_user_info
from amelie.tools.decorators import require_board, require_superuser, require_lid_or_oauth, require_committee
from amelie.tools.encodings import normalize_to_ascii
from amelie.tools.http import HttpResponseSendfile, HttpJSONResponse
from amelie.tools.logic import current_academic_year_with_holidays, current_association_year, association_year
from amelie.tools.mixins import DeleteMessageMixin, RequireBoardMixin, RequireCommitteeMixin
from amelie.tools.pdf import pdf_separator_page, pdf_membership_page, pdf_authorization_page

@require_board
def statistics(request):

    dt = None

    if 'dt' in request.GET:
        dt = parse_date(request.GET['dt'])

    if not dt:
        # The page will only render the Date input field
        return render(request, 'statistics/overview.html', locals())

    studies = Study.objects.all()
    per_study_total = 0
    per_study_rows = []
    for study in studies:
        count = Student.objects.filter(
            Q(person__membership__year=association_year(dt)),
            Q(studyperiod__end__isnull=True) | Q(studyperiod__end__gt=dt),
            Q(studyperiod__begin__isnull=False),
            Q(studyperiod__begin__lte=dt),
            Q(studyperiod__study=study)
        ).distinct().count()

        per_study_total += count
        per_study_rows.append({'name': study.name, 'abbreviation': study.abbreviation, 'count': count})
    per_study_rows = sorted(per_study_rows, key=lambda k: -k['count'])

    members_count = Person.objects.members_at(dt).count()
    active_members = Person.objects.active_members_at(dt)
    active_members_count = active_members.count()

    active_members_tcs = active_members.filter(
        Q(student__studyperiod__begin__isnull=False),
        Q(student__studyperiod__begin__lte=dt)
    ).annotate(
        # This makes sure only the latest studyperiod is used for the filter afterwards
        # Someone who is not studying anymore, but has studied CS at their latest studyperiod is counted
        student__latest_studyperiod = Max('student__studyperiod__begin')
    ).filter(
        Q(student__studyperiod__begin=F('student__latest_studyperiod')),
        Q(student__studyperiod__study__abbreviation__in=['B-TCS','M-CS'])
    ).distinct()
    active_members_tcs_count = len(active_members_tcs)

    active_members_bit = active_members.filter(
        Q(student__studyperiod__begin__isnull=False),
        Q(student__studyperiod__begin__lte=dt)
    ).annotate(
        # This makes sure only the latest studyperiod is used for the filter afterwards
        # Someone who is not studying anymore, but has studied BIT at their latest studyperiod is counted
        student__latest_studyperiod = Max('student__studyperiod__begin')
    ).filter(
        Q(student__studyperiod__begin=F('student__latest_studyperiod')),
        Q(student__studyperiod__study__abbreviation__in=['B-BIT','M-BIT'])
    ).distinct()
    active_members_bit_count = len(active_members_bit)

    other_studies = Study.objects.exclude(abbreviation__in=['B-TCS','M-CS','B-BIT','M-BIT']).values("abbreviation")

    active_members_other = active_members.filter(
        Q(student__studyperiod__begin__isnull=False),
        Q(student__studyperiod__begin__lte=dt)
    ).annotate(
        # This makes sure only the latest studyperiod is used for the filter afterwards
        student__latest_studyperiod_begin = Max('student__studyperiod__begin')
    ).filter(
        Q(student__studyperiod__begin=F('student__latest_studyperiod_begin')),
        # I know this is a very hacky way of excluding CS and BIT studies, but it doesn't work any other way...
        Q(student__studyperiod__study__abbreviation__in=[other_studies])
    ).distinct()
    active_members_other_count = len(active_members_other)

    percent_active_members = '{0:.2f}'.format((active_members_count*100.0)/members_count) if members_count != 0 else 0

    freshmen_bit = Person.objects.members_at(dt).filter(
        Q(membership__year=association_year(dt)),
        Q(student__studyperiod__study__abbreviation='B-BIT'),
        Q(student__studyperiod__begin__year=association_year(dt)),
        Q(student__studyperiod__end__isnull=True) | Q(student__studyperiod__end__gt=dt)
    ).distinct()

    freshmen_bit_count = freshmen_bit.count()
    active_freshmen_bit = [person for person in freshmen_bit if person in active_members]
    active_freshmen_bit_count = len(active_freshmen_bit)

    freshmen_tcs = Person.objects.members_at(dt).filter(
        Q(membership__year=association_year(dt)),
        Q(student__studyperiod__study__abbreviation='B-TCS'),
        Q(student__studyperiod__begin__year=association_year(dt)),
        Q(student__studyperiod__end__isnull=True) | Q(student__studyperiod__end__gt=dt)
    ).distinct()

    freshmen_tcs_count = freshmen_tcs.count()
    active_freshmen_tcs = [person for person in freshmen_tcs if person in active_members]
    active_freshmen_tcs_count = len(active_freshmen_tcs)

    freshmen_count = freshmen_bit_count + freshmen_tcs_count

    percent_active_freshmen = '{0:.2f}'.format(((active_freshmen_bit_count + active_freshmen_tcs_count) * 100.0) / active_members_count) if active_members_count != 0 else 0


    employee_count = Employee.objects.filter(
        Q(person__membership__year=association_year(dt)),
        Q(person__membership__ended__isnull=True) | Q(person__membership__ended__gt=dt)
    ).count()

    per_committee_total = 0
    per_committee_rows = []
    committees = Committee.objects.active_at(dt)
    committee_count = 0
    for committee in committees:
        count = Function.objects.filter(
            Q(committee=committee),
            Q(end__isnull=True) | Q(end__gt=dt),
            Q(begin__isnull=False),
            Q(begin__lte=dt)
        ).count()
        per_committee_total += count
        if count > 0:
            committee_count += 1
            per_committee_rows.append({'name': committee.name, 'count': count})

    per_commitee_total_ex_pools = per_committee_total
    pools = Committee.objects.active_at(dt).filter(category__name=settings.POOL_CATEGORY)
    for pool in pools:
        count = Function.objects.filter(
            Q(committee=pool),
            Q(end__isnull=True) | Q(end__gt=dt),
            Q(begin__isnull=False),
            Q(begin__lte=dt)
        ).count()
        per_commitee_total_ex_pools = per_commitee_total_ex_pools - count

    average_committees_ex_pools_per_active_member = '{0:.2f}'.format((per_commitee_total_ex_pools*1.0)/active_members_count) if active_members_count != 0 else 0
    average_committees_per_active_member = '{0:.2f}'.format((per_committee_total*1.0)/active_members_count) if active_members_count != 0 else 0

    per_active_member_total = {}
    for person in active_members:
        num = person.current_committees_at(dt).count()
        if num not in per_active_member_total.keys():
            per_active_member_total[num] = 0
        per_active_member_total[num] += 1
    sorted(per_active_member_total.keys())

    per_active_member_total_6plus = active_members_count - per_active_member_total.get(1, 0) - \
        per_active_member_total.get(2, 0) - per_active_member_total.get(3, 0) - \
        per_active_member_total.get(4, 0) - per_active_member_total.get(5, 0)

    international_members = Person.objects.members_at(dt).filter(international_member=Person.InternationalChoices.YES).distinct()
    international_members_count = international_members.count()

    active_international_members_count = len([member for member in international_members if member in active_members])

    members = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    members_ex_pools = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    for member in active_members:
        num = member.current_committees_at(dt).count()
        num_ex_pools = member.current_committees_at(dt).exclude(category__name=settings.POOL_CATEGORY).count()

        if num not in members.keys():
            members[num] = [member]
        else:
            members[num].append(member)

        if num_ex_pools not in members_ex_pools.keys():
            members_ex_pools[num_ex_pools] = [member]
        else:
            members_ex_pools[num_ex_pools].append(member)

    committees_per_member = []
    for n in range(1, 6):
        res = {'n': n,
               'total': len(members[n]),
               'total_ex': len(members_ex_pools[n]),
               'board': len([x for x in members[n] if x.was_board_at(dt)]),
               'board_ex': len([x for x in members_ex_pools[n] if x.was_board_at(dt)]),
               'freshman': len([x for x in members[n] if x in freshmen_tcs or x in freshmen_bit]),
               'freshman_ex': len([x for x in members_ex_pools[n] if x in freshmen_tcs or x in freshmen_bit]),
               'international': len([x for x in members[n] if x in international_members]),
               'international_ex': len([x for x in members_ex_pools[n] if x in international_members]),
               'tcs': len([x for x in members[n] if x in active_members_tcs]),
               'tcs_ex': len([x for x in members_ex_pools[n] if x in active_members_tcs]),
               'bit': len([x for x in members[n] if x in active_members_bit]),
               'bit_ex': len([x for x in members_ex_pools[n] if x in active_members_bit]),
               'other': len([x for x in members[n] if x not in active_members_tcs and x not in active_members_bit]),
               'other_ex': len([x for x in members_ex_pools[n] if x not in active_members_tcs and x not in active_members_bit])}
        committees_per_member.append(res)

    six_or_more_data = [members[x] for x in members.keys() if x > 5]
    six_or_more_data_ex = [members_ex_pools[x] for x in members_ex_pools.keys() if x > 5]
    six_or_more = [person for sublist in six_or_more_data for person in sublist]
    six_or_more_ex = [person for sublist in six_or_more_data_ex for person in sublist]
    res = {'n': _('6 or more'),
           'total': len(six_or_more),
           'total_ex': len(six_or_more_ex),
            'board': len([x for x in six_or_more if x.was_board_at(dt)]),
            'board_ex': len([x for x in six_or_more_ex if x.was_board_at(dt)]),
           'freshman': len([x for x in six_or_more if x in freshmen_tcs or x in freshmen_bit]),
           'freshman_ex': len([x for x in six_or_more_ex if x in freshmen_tcs or x in freshmen_bit]),
           'international': len([x for x in six_or_more if x in international_members]),
           'international_ex': len([x for x in six_or_more_ex if x in international_members]),
           'tcs': len([x for x in six_or_more if x in active_members_tcs]),
           'tcs_ex': len([x for x in six_or_more_ex if x in active_members_tcs]),
           'bit': len([x for x in six_or_more if x in active_members_bit]),
           'bit_ex': len([x for x in six_or_more_ex if x in active_members_bit]),
           'other': len([x for x in six_or_more if x not in active_members_tcs and x not in active_members_bit]),
           'other_ex': len([x for x in six_or_more_ex if x not in active_members_tcs and x not in active_members_bit])}
    committees_per_member.append(res)

    res = {'n': _('total'),
           'total': sum([x['total'] for x in committees_per_member]),
           'total_ex': sum([x['total_ex'] for x in committees_per_member]),
           'board': sum([x['board'] for x in committees_per_member]),
           'board_ex': sum([x['board_ex'] for x in committees_per_member]),
           'freshman': sum([x['freshman'] for x in committees_per_member]),
           'freshman_ex': sum([x['freshman_ex'] for x in committees_per_member]),
           'international': sum([x['international'] for x in committees_per_member]),
           'international_ex': sum([x['international_ex'] for x in committees_per_member]),
           'tcs': sum([x['tcs'] for x in committees_per_member]),
           'tcs_ex': sum([x['tcs_ex'] for x in committees_per_member]),
           'bit': sum([x['bit'] for x in committees_per_member]),
           'bit_ex': sum([x['bit_ex'] for x in committees_per_member]),
           'other': sum([x['other'] for x in committees_per_member]),
           'other_ex': sum([x['other_ex'] for x in committees_per_member])}
    committees_per_member.append(res)

    return render(request, 'statistics/overview.html', locals())


@require_board
def payment_statistics(request, start_year=2012):
    rows = []
    payment_types = PaymentType.objects.all()
    membership_types = MembershipType.objects.all()
    for mtype in membership_types:
        cells = [mtype, ]
        count = 0
        for ptype in payment_types:
            memberships = Membership.objects.filter(year=start_year, payment__payment_type=ptype, type=mtype)
            mcount = memberships.count()
            count += mcount
            cells.append(mcount)
        cells.append(count)
        rows.append(cells)
    ziprows = zip(*rows)
    totalcells = map(sum, list(zip(*rows))[1:])
    return render(request, 'statistics/payments.html', locals())


@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_view(request, id, slug):
    obj = get_object_or_404(Person, id=id, slug=slug)
    preference_categories = PreferenceCategory.objects.all()
    alters_data = True
    date_old_mandates = settings.DATE_PRE_SEPA_AUTHORIZATIONS
    try:
        accounts = get_user_info(obj)
    except Exception as e:
        # Keycloak not reachable or running in non-production (not configured)
        accounts = []

    can_be_anonymized, unable_to_anonymize_reasons = _person_can_be_anonymized(obj)
    is_roomduty = request.person.is_room_duty()

    return render(request, "person.html", locals())


@require_committee(settings.ROOM_DUTY_ABBREVIATION)
@transaction.atomic
def person_edit(request, id, slug):
    person = get_object_or_404(Person, id=id)
    form = PersonDataForm(instance=person, data=request.POST or None, files=request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(person.get_absolute_url())

    return render(request, "person_edit_data.html", locals())


def _person_can_be_anonymized(person):
    # Check if this person can be anonymized and collect reasons why not.
    unable_to_anonymize_reasons = []

    if person.is_member_strict():
        unable_to_anonymize_reasons.append(_("This person still has an active (unterminated) membership."))

    for membership in person.membership_set.all():
        if not hasattr(membership, 'payment'):
            unable_to_anonymize_reasons.append(_("This person has not paid one of their memberships "
                                                 "({year}/{next_year} {type}).".format(
                year=membership.year, next_year=membership.year + 1, type=membership.type
            )))
    # Date where new SEPA authorizations came into effect.
    begin = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=timezone.utc)
    personal_tab_credit = Transaction.objects.filter(person=person, date__gte=begin).aggregate(Sum('price'))[
        'price__sum'] or Decimal('0.00')
    if personal_tab_credit != 0:
        unable_to_anonymize_reasons.append(_("This person still has an outstanding balance on their personal tab."))

    if person.participation_set.filter(event__end__gte=timezone.now()):
        unable_to_anonymize_reasons.append(_("This person isn't enrolled for one or more future activities."))

    can_be_anonymized = len(unable_to_anonymize_reasons) == 0

    return can_be_anonymized, unable_to_anonymize_reasons


@require_board
@transaction.atomic
def person_anonymize(request, id, slug):
    person = get_object_or_404(Person, id=id)
    sentinel_person = get_object_or_404(Person, id=settings.ANONIMIZATION_SENTINEL_PERSON_ID)

    can_be_anonymized, reasons = _person_can_be_anonymized(person)
    if not can_be_anonymized:
        raise ValueError(_("This person cannot be anonymized because of the following reasons:\n"
                           "{}".format("\n".join("- {}".format(reason) for reason in reasons))))

    # Remove from all claudia groups and anonymize mapping
    claudia_mapping = Mapping.find(person)
    if claudia_mapping is not None:
        claudia_mapping.extra_members.all().delete()
        claudia_mapping.extra_groupmemberships.all().delete()
        claudia_mapping.extra_personal_aliases.all().delete()
        claudia_mapping.name = "Anomymous"
        claudia_mapping.email = "anonymous@inter-actief.net"
        claudia_mapping.adname = ""
        claudia_mapping.save()

    # Anonymize enrollments
    person.participation_set.all().update(person=sentinel_person)

    # Anonymize room duties, pools and availabilities
    pools = person.room_duty_pools.all()
    for pool in pools:
        pool.unsorted_persons.remove(person)
    duties = person.room_duties.all()
    for duty in duties:
        duty.participant_set.remove(person)
    person.roomdutyavailability_set.all().delete()

    # Anonymize news
    person.newsitem_set.all().update(author=None)

    # Anonymize oauth2
    if hasattr(person, 'bindtoken'):
        person.bindtoken.delete()
    if hasattr(person, 'user'):
        AccessToken.objects.filter(user=person.user).delete()
        Grant.objects.filter(user=person.user).delete()
        FCMDevice.objects.filter(user=person.user).delete()

    # Anonymize education
    person.complaint_set.all().update(reporter=sentinel_person)
    person.complaintcomment_set.all().update(person=sentinel_person)
    for also_affects_me in person.personen.all():
        also_affects_me.people.remove(person)
    person.vote_set.all().update(person=sentinel_person)

    # Anonymize personal tab
    # We don't want to anonymize transactions and authorizations,
    # as they are needed for financial reasons
    # (Transactions need to be kept 7 years, authorizations for 2 years after they expire,
    # and authorizations are anonymized and cleaned up by the board every year)
    person.rfidcard_set.all().delete()

    # Anonymize member object if it exists
    if person.is_student():
        person.student.studyperiod_set.all().delete()
        person.student.delete()

    if person.is_employee():
        person.employee.delete()

    # The name is kept unanonymized, because we want to keep our old active member data
    # for the association archive, and the functions use the name of the person object.
    # Memberships are also kept for archival reasons.
    person.initials = ""
    person.notes = ""
    person.gender = Person.GenderTypes.UNKNOWN
    person.international_member = Person.InternationalChoices.UNKNOWN
    person.date_of_birth = None
    person.address = "Anonymous"
    person.postal_code = "7500AE"
    person.city = "Anonymous"
    person.country = "Anonymous"
    person.email_address = None
    person.telephone = ""
    person.address_parents = ""
    person.postal_code_parents = ""
    person.city_parents = ""
    person.country_parents = ""
    person.email_address_parents = ""
    person.can_use_parents_address = False
    person.account_name = ""
    person.webmaster = False
    person.preferences.clear()
    if person.user:
        person.user.email = "anonymous@inter-actief.net"
        person.user.save()
        person.user = None
    if person.picture:
        person.picture.delete()
    person.save()

    return render(request, 'person_anonymization_success.html', {'person': person})


class RegisterNewGeneralWizardView(RequireCommitteeMixin, SessionWizardView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_registration_form_general.html"
    form_list = [RegistrationFormPersonalDetails, RegistrationFormStepMemberContactDetails,
                 RegistrationFormStepGeneralStudyDetails, RegistrationFormStepGeneralMembershipDetails,
                 RegistrationFormStepAuthorizationDetails, RegistrationFormStepPersonalPreferences,
                 RegistrationFormStepFinalCheck]

    def get_context_data(self, form, **kwargs):
        context = super(RegisterNewGeneralWizardView, self).get_context_data(form=form, **kwargs)

        # Inject the type of registration form (Freshmen, General or Employee)
        context['form_type'] = 'general'

        # Inject the costs of the different membership types for use in the templates
        context['year_member_costs'] = MembershipType.objects.get(name_en='Primary yearlong').price
        context['study_long_member_costs'] = MembershipType.objects.get(name_en='Studylong (first year)').price
        context['secondary_member_costs'] = MembershipType.objects.get(name_en='Secondary yearlong').price

        # Inject the current progress percentage
        context['progress_bar_percentage'] = str((self.steps.step1 / self.steps.count) * 100)

        # If we are on the last step, inject the form data of all forms to show in an overview.
        if self.steps.step1 == 7:
            context['form_data'] = self.get_all_cleaned_data()
            # Get the correct display format for the preferred language
            language_dict = {l[0]: _(l[1]) for l in settings.LANGUAGES}
            context['form_data']['preferred_language'] = language_dict.get(context['form_data']['preferred_language'],
                                                                           context['form_data']['preferred_language'])
            context['all_preferences'] = Preference.objects.exclude(first_time=False)
        return context

    @transaction.atomic
    def done(self, form_list, **kwargs):
        # Get all cleaned data for all forms in one merged dictionary
        cleaned_data = self.get_all_cleaned_data()

        # Construct the Person object
        person = Person(
            first_name=cleaned_data['first_name'],
            last_name_prefix=cleaned_data['last_name_prefix'],
            last_name=cleaned_data['last_name'],
            initials=cleaned_data['initials'],
            gender=cleaned_data['gender'],
            preferred_language=cleaned_data['preferred_language'],
            international_member=cleaned_data['international_member'],
            date_of_birth=cleaned_data['date_of_birth'],
            address=cleaned_data['address'],
            postal_code=cleaned_data['postal_code'],
            city=cleaned_data['city'],
            country=cleaned_data['country'],
            email_address=cleaned_data['email_address'],
            telephone=cleaned_data['telephone'],
        )
        person.save()
        # Preferences (m2m relations) can only be added after a person has been saved.
        person.preferences.set(cleaned_data['preferences'])
        person.save()

        # Add preferences that should be enabled by default and are not shown during the first time
        for p in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(p)

        # Sanitize account holder name
        sanitized_account_holder_name = person.initials_last_name()
        try:
            SEPA_CHAR_VALIDATOR(sanitized_account_holder_name)
        except ValidationError:
            sanitized_account_holder_name = normalize_to_ascii(sanitized_account_holder_name)

        # Add contribution authorization if wanted
        if 'authorization_contribution' in cleaned_data and cleaned_data['authorization_contribution']:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today()
            )
            contribution_authorization.save()

        # Add other authorization if wanted
        if 'authorization_other' in cleaned_data and cleaned_data['authorization_other']:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today())
            authorization_other.save()

        # Add membership details
        membership = Membership(member=person, type=cleaned_data['membership'],
                                year=current_association_year())
        membership.save()

        # Add student details
        student = Student(person=person, number=cleaned_data['student_number'])
        student.save()

        # Add study periods
        for study in cleaned_data['study']:
            study_period = StudyPeriod(student=student, study=study,
                                       begin=datetime.date(cleaned_data['generation'], 9, 1))
            study_period.save()

        # Render the enrollment forms to PDF for printing
        from amelie.tools.pdf import pdf_enrollment_form
        buffer = BytesIO()
        pdf_enrollment_form(buffer, person, membership)
        pdf = buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')

class RegisterNewExternalWizardView(RequireCommitteeMixin, SessionWizardView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_registration_form_external.html"
    form_list = [RegistrationFormPersonalDetails, RegistrationFormStepMemberContactDetails,
                 RegistrationFormStepAuthorizationDetails, RegistrationFormStepPersonalPreferences,
                 RegistrationFormStepFinalCheck]

    def get_context_data(self, form, **kwargs):
        context = super(RegisterNewExternalWizardView, self).get_context_data(form=form, **kwargs)

        # Inject the type of registration form (Freshmen, General, External or Employee)
        context['form_type'] = 'external'

        # Inject the costs of the different membership types for use in the templates
        context['year_member_costs'] = MembershipType.objects.get(name_en='Primary yearlong').price

        # Inject the current progress percentage
        context['progress_bar_percentage'] = str((self.steps.step1 / self.steps.count) * 100)

        # If we are on the last step, inject the form data of all forms to show in an overview.
        if self.steps.step1 == 5:
            context['form_data'] = self.get_all_cleaned_data()
            # Get the correct display format for the preferred language
            language_dict = {l[0]: _(l[1]) for l in settings.LANGUAGES}
            context['form_data']['preferred_language'] = language_dict.get(context['form_data']['preferred_language'],
                                                                           context['form_data']['preferred_language'])
            context['all_preferences'] = Preference.objects.exclude(first_time=False)
        return context

    @transaction.atomic
    def done(self, form_list, **kwargs):
        # Get all cleaned data for all forms in one merged dictionary
        cleaned_data = self.get_all_cleaned_data()

        # Construct the Person object
        person = Person(
            first_name=cleaned_data['first_name'],
            last_name_prefix=cleaned_data['last_name_prefix'],
            last_name=cleaned_data['last_name'],
            initials=cleaned_data['initials'],
            gender=cleaned_data['gender'],
            preferred_language=cleaned_data['preferred_language'],
            international_member=cleaned_data['international_member'],
            date_of_birth=cleaned_data['date_of_birth'],
            address=cleaned_data['address'],
            postal_code=cleaned_data['postal_code'],
            city=cleaned_data['city'],
            country=cleaned_data['country'],
            email_address=cleaned_data['email_address'],
            telephone=cleaned_data['telephone'],
        )
        person.save()
        # Preferences (m2m relations) can only be added after a person has been saved.
        person.preferences.set(cleaned_data['preferences'])
        person.save()

        # Add preferences that should be enabled by default and are not shown during the first time
        for p in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(p)

        # Sanitize account holder name
        sanitized_account_holder_name = person.initials_last_name()
        try:
            SEPA_CHAR_VALIDATOR(sanitized_account_holder_name)
        except ValidationError:
            sanitized_account_holder_name = normalize_to_ascii(sanitized_account_holder_name)

        # Add contribution authorization if wanted
        if 'authorization_contribution' in cleaned_data and cleaned_data['authorization_contribution']:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today()
            )
            contribution_authorization.save()

        # Add other authorization if wanted
        if 'authorization_other' in cleaned_data and cleaned_data['authorization_other']:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today())
            authorization_other.save()

        # Add membership details
        membership = Membership(member=person, type=MembershipType.objects.get(name_en='Primary yearlong'),
                                year=current_association_year())
        membership.save()

        # Create user for logging in
        person.get_or_create_user(f"e{person.pk}")

        # Send OAuth token to registered email
        link_code = get_oauth_link_code(person)
        send_oauth_link_code_email(self.request, person, link_code)

        # Render the enrollment forms to PDF for printing
        from amelie.tools.pdf import pdf_enrollment_form
        buffer = BytesIO()
        pdf_enrollment_form(buffer, person, membership)
        pdf = buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')


class RegisterNewEmployeeWizardView(RequireCommitteeMixin, SessionWizardView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_registration_form_employee.html"
    form_list = [RegistrationFormPersonalDetailsEmployee, RegistrationFormStepMemberContactDetails,
                 RegistrationFormStepEmployeeDetails, RegistrationFormStepEmployeeMembershipDetails,
                 RegistrationFormStepAuthorizationDetails, RegistrationFormStepPersonalPreferences,
                 RegistrationFormStepFinalCheck]

    def get_context_data(self, form, **kwargs):
        context = super(RegisterNewEmployeeWizardView, self).get_context_data(form=form, **kwargs)

        # Inject the type of registration form (Freshmen, General or Employee)
        context['form_type'] = 'employee'

        # Inject the costs of the different membership types for use in the templates
        context['employee_member_costs'] = MembershipType.objects.get(name_en='Employee yearlong').price

        # Inject the current progress percentage
        context['progress_bar_percentage'] = str((self.steps.step1 / self.steps.count) * 100)

        # If we are on the last step, inject the form data of all forms to show in an overview.
        if self.steps.step1 == 7:
            context['form_data'] = self.get_all_cleaned_data()
            # Get the correct display format for the preferred language
            language_dict = {l[0]: _(l[1]) for l in settings.LANGUAGES}
            context['form_data']['preferred_language'] = language_dict.get(context['form_data']['preferred_language'],
                                                                           context['form_data']['preferred_language'])
            context['all_preferences'] = Preference.objects.exclude(first_time=False)
        return context

    @transaction.atomic
    def done(self, form_list, **kwargs):
        # Get all cleaned data for all forms in one merged dictionary
        cleaned_data = self.get_all_cleaned_data()

        # Construct the Person object
        person = Person(
            first_name=cleaned_data['first_name'],
            last_name_prefix=cleaned_data['last_name_prefix'],
            last_name=cleaned_data['last_name'],
            initials=cleaned_data['initials'],
            gender=cleaned_data['gender'],
            preferred_language=cleaned_data['preferred_language'],
            date_of_birth=cleaned_data['date_of_birth'],
            address=cleaned_data['address'],
            postal_code=cleaned_data['postal_code'],
            city=cleaned_data['city'],
            country=cleaned_data['country'],
            email_address=cleaned_data['email_address'],
            telephone=cleaned_data['telephone'],
        )
        person.save()
        # Preferences (m2m relations) can only be added after a person has been saved.
        person.preferences.set(cleaned_data['preferences'])
        person.save()

        # Add preferences that should be enabled by default and are not shown during the first time
        for p in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(p)

        # Sanitize account holder name
        sanitized_account_holder_name = person.initials_last_name()
        try:
            SEPA_CHAR_VALIDATOR(sanitized_account_holder_name)
        except ValidationError:
            sanitized_account_holder_name = normalize_to_ascii(sanitized_account_holder_name)

        # Add contribution authorization if wanted
        if 'authorization_contribution' in cleaned_data and cleaned_data['authorization_contribution']:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today()
            )
            contribution_authorization.save()

        # Add other authorization if wanted
        if 'authorization_other' in cleaned_data and cleaned_data['authorization_other']:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today())
            authorization_other.save()

        # Add membership details
        membership = Membership(member=person, type=cleaned_data['membership'],
                                year=current_association_year())
        membership.save()

        # Add employee details
        employee = Employee(person=person, number=cleaned_data['employee_number'])
        employee.save()

        # Render the enrollment forms to PDF for printing
        from amelie.tools.pdf import pdf_enrollment_form
        buffer = BytesIO()
        pdf_enrollment_form(buffer, person, membership)
        pdf = buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')


class RegisterNewFreshmanWizardView(RequireCommitteeMixin, SessionWizardView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_registration_form_freshmen.html"
    form_list = [RegistrationFormPersonalDetails, RegistrationFormStepMemberContactDetails,
                 RegistrationFormStepParentsContactDetails, RegistrationFormStepFreshmenStudyDetails,
                 RegistrationFormStepFreshmenMembershipDetails, RegistrationFormStepAuthorizationDetails,
                 RegistrationFormStepPersonalPreferences, RegistrationFormStepFinalCheck]

    def get_context_data(self, form, **kwargs):
        context = super(RegisterNewFreshmanWizardView, self).get_context_data(form=form, **kwargs)

        # Inject the type of registration form (Freshmen, General or Employee)
        context['form_type'] = 'freshmen'

        # Inject the costs of the different membership types for use in the templates
        context['year_member_costs'] = MembershipType.objects.get(name_en='Primary yearlong').price
        context['study_long_member_costs'] = MembershipType.objects.get(name_en='Studylong (first year)').price

        # Inject the current progress percentage
        context['progress_bar_percentage'] = str((self.steps.step1 / self.steps.count) * 100)

        # If we are on the last step, inject the form data of all forms to show in an overview.
        if self.steps.step1 == 8:
            context['form_data'] = self.get_all_cleaned_data()
            # Get the correct display format for the preferred language
            language_dict = {l[0]: _(l[1]) for l in settings.LANGUAGES}
            context['form_data']['preferred_language'] = language_dict.get(context['form_data']['preferred_language'],
                                                                           context['form_data']['preferred_language'])
            context['all_preferences'] = Preference.objects.exclude(first_time=False)
        return context

    @transaction.atomic
    def done(self, form_list, **kwargs):
        # Get all cleaned data for all forms in one merged dictionary
        cleaned_data = self.get_all_cleaned_data()

        # Construct the Person object
        person = Person(
            first_name=cleaned_data['first_name'],
            last_name_prefix=cleaned_data['last_name_prefix'],
            last_name=cleaned_data['last_name'],
            initials=cleaned_data['initials'],
            gender=cleaned_data['gender'],
            preferred_language=cleaned_data['preferred_language'],
            international_member=cleaned_data['international_member'],
            date_of_birth=cleaned_data['date_of_birth'],
            address=cleaned_data['address'],
            postal_code=cleaned_data['postal_code'],
            city=cleaned_data['city'],
            country=cleaned_data['country'],
            email_address=cleaned_data['email_address'],
            telephone=cleaned_data['telephone'],
            address_parents=cleaned_data['address_parents'],
            postal_code_parents=cleaned_data['postal_code_parents'],
            city_parents=cleaned_data['city_parents'],
            country_parents=cleaned_data['country_parents'],
            email_address_parents=cleaned_data['email_address_parents'],
            can_use_parents_address=cleaned_data['can_use_parents_address'],
        )
        person.save()
        # Preferences (m2m relations) can only be added after a person has been saved.
        person.preferences.set(cleaned_data['preferences'])
        person.save()

        # Add preferences that should be enabled by default and are not shown during the first time
        for p in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(p)

        # Sanitize account holder name
        sanitized_account_holder_name = person.initials_last_name()
        try:
            SEPA_CHAR_VALIDATOR(sanitized_account_holder_name)
        except ValidationError:
            sanitized_account_holder_name = normalize_to_ascii(sanitized_account_holder_name)

        # Add contribution authorization if wanted
        if 'authorization_contribution' in cleaned_data and cleaned_data['authorization_contribution']:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today()
            )
            contribution_authorization.save()

        # Add other authorization if wanted
        if 'authorization_other' in cleaned_data and cleaned_data['authorization_other']:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=person,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today())
            authorization_other.save()

        # Add membership details
        membership = Membership(member=person, type=cleaned_data['membership'],
                                year=current_association_year())
        membership.save()

        # Add student details
        student = Student(person=person, number=cleaned_data['student_number'])
        student.save()

        # Add study periods
        for study in cleaned_data['study']:
            study_period = StudyPeriod(student=student, study=study,
                                       begin=datetime.date(current_academic_year_with_holidays(), 9, 1),
                                       dogroup=cleaned_data['dogroup'])
            study_period.save()

        # Render the enrollment forms to PDF for printing
        from amelie.tools.pdf import pdf_enrollment_form
        buffer = BytesIO()
        pdf_enrollment_form(buffer, person, membership)
        pdf = buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')


class PreRegisterNewFreshmanWizardView(SessionWizardView):
    template_name = "person_registration_form_preregister_freshmen.html"
    form_list = [RegistrationFormPersonalDetails, RegistrationFormStepMemberContactDetails,
                 RegistrationFormStepParentsContactDetails, RegistrationFormStepFreshmenStudyDetails,
                 RegistrationFormStepFreshmenMembershipDetails, RegistrationFormStepAuthorizationDetails,
                 RegistrationFormStepPersonalPreferences, RegistrationFormStepFinalCheck]

    def get_context_data(self, form, **kwargs):
        context = super(PreRegisterNewFreshmanWizardView, self).get_context_data(form=form, **kwargs)

        # Inject the type of registration form (Pre-enrollment, Freshmen or General)
        context['form_type'] = 'pre_enroll_freshmen'

        # Inject the costs of the different membership types for use in the templates
        context['year_member_costs'] = MembershipType.objects.get(name_en='Primary yearlong').price
        context['study_long_member_costs'] = MembershipType.objects.get(name_en='Studylong (first year)').price

        # Inject the current progress percentage
        context['progress_bar_percentage'] = str((self.steps.step1 / self.steps.count) * 100)

        # If we are on the last step, inject the form data of all forms to show in an overview.
        if self.steps.step1 == 8:
            context['form_data'] = self.get_all_cleaned_data()
            # Get the correct display format for the preferred language
            language_dict = {l[0]: _(l[1]) for l in settings.LANGUAGES}
            context['form_data']['preferred_language'] = language_dict.get(context['form_data']['preferred_language'],
                                                                           context['form_data']['preferred_language'])
            context['all_preferences'] = Preference.objects.exclude(first_time=False)
        return context

    @transaction.atomic
    def done(self, form_list, **kwargs):
        # Get all cleaned data for all forms in one merged dictionary
        cleaned_data = self.get_all_cleaned_data()

        # Construct the Person object
        person = UnverifiedEnrollment(
            # Person details
            first_name=cleaned_data['first_name'],
            last_name_prefix=cleaned_data['last_name_prefix'],
            last_name=cleaned_data['last_name'],
            initials=cleaned_data['initials'],
            gender=cleaned_data['gender'],
            preferred_language=cleaned_data['preferred_language'],
            international_member=cleaned_data['international_member'],
            date_of_birth=cleaned_data['date_of_birth'],
            address=cleaned_data['address'],
            postal_code=cleaned_data['postal_code'],
            city=cleaned_data['city'],
            country=cleaned_data['country'],
            email_address=cleaned_data['email_address'],
            telephone=cleaned_data['telephone'],
            address_parents=cleaned_data['address_parents'],
            postal_code_parents=cleaned_data['postal_code_parents'],
            city_parents=cleaned_data['city_parents'],
            country_parents=cleaned_data['country_parents'],
            email_address_parents=cleaned_data['email_address_parents'],
            can_use_parents_address=cleaned_data['can_use_parents_address'],

            # Membership details
            membership_type=cleaned_data['membership'],
            membership_year=current_association_year(),

            # Study details
            student_number=cleaned_data['student_number'],
            study_start_date=datetime.date(current_academic_year_with_holidays(), 9, 1),
            dogroup=cleaned_data['dogroup'],
        )
        person.save()

        # Preferences and studies (m2m relations) can only be added after a person has been saved.
        person.preferences.set(cleaned_data['preferences'])
        person.save()

        # Add preferences that should be enabled by default and are not shown during the first time
        for p in Preference.objects.filter(first_time=False, default=True):
            person.preferences.add(p)

        # Sanitize account holder name
        sanitized_account_holder_name = person.initials_last_name()
        try:
            SEPA_CHAR_VALIDATOR(sanitized_account_holder_name)
        except ValidationError:
            sanitized_account_holder_name = normalize_to_ascii(sanitized_account_holder_name)

        # Add contribution authorization if wanted
        if 'authorization_contribution' in cleaned_data and cleaned_data['authorization_contribution']:
            contribution_authorization = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, contribution=True),
                person=None,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today()
            )
            contribution_authorization.save()
            person.authorizations.add(contribution_authorization)

        # Add other authorization if wanted
        if 'authorization_other' in cleaned_data and cleaned_data['authorization_other']:
            authorization_other = Authorization(
                authorization_type=AuthorizationType.objects.get(active=True, consumptions=True,
                                                                 activities=True, other_payments=True),
                person=None,
                iban=cleaned_data['iban'],
                bic=cleaned_data['bic'],
                account_holder_name=sanitized_account_holder_name,
                start_date=date.today())
            authorization_other.save()
            person.authorizations.add(authorization_other)

        # Add studies
        for study in cleaned_data['study']:
            person.studies.add(study)

        # Generate PDF enrollment forms
        from amelie.tools.pdf import pdf_enrollment_form
        buffer = BytesIO()
        pdf_enrollment_form(buffer, person, person.membership_type)
        pdf = buffer.getvalue()

        # Send welcome e-mail with forms attached.
        from amelie.iamailer import MailTask
        from amelie.tools.mail import PersonRecipient
        welcome_mail = MailTask(from_='I.C.T.S.V. Inter-Actief <secretary@inter-actief.net>',
                                template_name='members/preregistration_welcome.mail',
                                report_to='I.C.T.S.V. Inter-Actief <secretary@inter-actief.net>',
                                report_language='nl',
                                report_always=False)
        person_slug = slugify(person.incomplete_name())

        welcome_mail.add_recipient(PersonRecipient(recipient=person, context={}, attachments=[
            ('inter-actief_enrollment_{}.pdf'.format(person_slug), pdf, 'application/pdf')
        ]))
        welcome_mail.send()

        # Redirect to the success page
        return redirect('members:person_preregister_complete')


class PreRegistrationCompleteView(TemplateView):
    template_name = "person_registration_form_preregister_complete.html"


class PreRegistrationStatus(RequireCommitteeMixin, TemplateView):
    template_name = "preregistration_status.html"
    abbreviation = settings.ROOM_DUTY_ABBREVIATION

    def get_context_data(self, **kwargs):
        context = super(PreRegistrationStatus, self).get_context_data(**kwargs)

        enrollments = UnverifiedEnrollment.objects.all()
        enrollments = sorted(enrollments, key=lambda x: str(x.dogroup) + " " + str(x.sortable_name()))
        context['pre_enrollments'] = enrollments

        context['delete_enabled'] = self.request.GET.get("deletion", False)

        # If eid is given in GET params, add enrollment context variable
        if self.request.GET.get('eid', None) is not None:
            context['enrollment'] = UnverifiedEnrollment.objects.get(pk=self.request.GET.get('eid', None))

        return context

    def get(self, request, *args, **kwargs):
        pre_enrollment_id = request.GET.get('eid', None)
        action = request.GET.get('action', None)
        if pre_enrollment_id is not None:
            pre_enrollment = UnverifiedEnrollment.objects.get(pk=pre_enrollment_id)
        else:
            pre_enrollment = None
        if action is not None:
            if action == "accept" and pre_enrollment is not None:
                # Create a Person, Student, Membership, etc. using the data from the UnverifiedEnrollment,
                # then transfer the wanted authorizations to that person, and delete the pre-enrollment.

                # Construct the Person object
                person = Person(
                    first_name=pre_enrollment.first_name,
                    last_name_prefix=pre_enrollment.last_name_prefix,
                    last_name=pre_enrollment.last_name,
                    initials=pre_enrollment.initials,
                    gender=pre_enrollment.gender,
                    preferred_language=pre_enrollment.preferred_language,
                    international_member=pre_enrollment.international_member,
                    date_of_birth=pre_enrollment.date_of_birth,
                    address=pre_enrollment.address,
                    postal_code=pre_enrollment.postal_code,
                    city=pre_enrollment.city,
                    country=pre_enrollment.country,
                    email_address=pre_enrollment.email_address,
                    telephone=pre_enrollment.telephone,
                    address_parents=pre_enrollment.address_parents,
                    postal_code_parents=pre_enrollment.postal_code_parents,
                    city_parents=pre_enrollment.city_parents,
                    country_parents=pre_enrollment.country_parents,
                    email_address_parents=pre_enrollment.email_address_parents,
                    can_use_parents_address=pre_enrollment.can_use_parents_address,
                )
                person.save()
                # Preferences (m2m relations) can only be added after a person has been saved.
                person.preferences.set(pre_enrollment.preferences.all())
                person.save()

                # Add membership details
                membership = Membership(member=person, type=pre_enrollment.membership_type,
                                        year=pre_enrollment.membership_year)
                membership.save()

                # Add student details
                student = Student(person=person, number=pre_enrollment.student_number)
                student.save()

                # Add study periods
                for study in pre_enrollment.studies.all():
                    study_period = StudyPeriod(student=student, study=study,
                                               begin=pre_enrollment.study_start_date,
                                               dogroup=pre_enrollment.dogroup)
                    study_period.save()

                # Add authorizations and activate them.
                for authorization in pre_enrollment.authorizations.all():
                    authorization.person = person
                    authorization.is_signed = True
                    authorization.save()

                # Delete the pre-enrollment
                pre_enrollment.delete()

                # Set message
                messages.info(self.request, "Pre-registration of {} activated!".format(person.incomplete_name()))

                # Redirect to the normal page
                return redirect('members:preregistration_status')

            elif action == "print" and pre_enrollment is not None:
                from amelie.tools.pdf import pdf_enrollment_form
                buffer = BytesIO()
                pdf_enrollment_form(buffer, pre_enrollment, pre_enrollment.membership_type)
                pdf = buffer.getvalue()
                return HttpResponse(pdf, content_type='application/pdf')
            elif action == "delete" and pre_enrollment is not None:
                self.template_name = "preregistration_delete_confirm.html"
            elif action == "delete-sure" and pre_enrollment is not None:
                # Save name for notification
                name = pre_enrollment.incomplete_name()
                # Delete the authorizations beloning to this pre-registration
                # (to avoid having unactivated, anonymous authorizations in the system)
                for authorization in pre_enrollment.authorizations.all():
                    authorization.delete()
                # Delete the pre-enrollment
                pre_enrollment.delete()
                # Set message
                messages.info(self.request, "Pre-registration of {} deleted!".format(name))
                # Redirect to the normal page
                return redirect('members:preregistration_status')

        return super(PreRegistrationStatus, self).get(request, *args, **kwargs)


class PreRegistrationPrintDogroup(RequireCommitteeMixin, TemplateView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION

    def get(self, request, *args, **kwargs):
        pre_enrollment_dogroup_id = request.GET.get('did', None)
        if pre_enrollment_dogroup_id is not None:
            pre_enrollments_dogroup = UnverifiedEnrollment.objects.filter(dogroup__pk=pre_enrollment_dogroup_id)
        else:
            pre_enrollments_dogroup = []

        # Create PDF object
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        pdf_buffer = BytesIO()
        pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=A4)

        for enrollment in pre_enrollments_dogroup:

            # Add forms to PDF
            pdf_membership_page(pdf_canvas, enrollment, enrollment.membership_type)
            for authorization in enrollment.authorizations.all():
                pdf_authorization_page(pdf_canvas, (authorization, enrollment))

        pdf_canvas.save()
        pdf = pdf_buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')


class PreRegistrationPrintAll(RequireCommitteeMixin, FormView):
    template_name = "preregistration_print_all.html"
    form_class = PreRegistrationPrintAllForm
    abbreviation = settings.ROOM_DUTY_ABBREVIATION

    def form_valid(self, form):
        sort_by = form.cleaned_data['sort_by']
        group_dogroups = form.cleaned_data['group_by_dogroup']
        sign_date = form.cleaned_data['signing_date']

        # Retrieve pre-enrollments
        pre_enrollments = UnverifiedEnrollment.objects.all().prefetch_related('authorizations', 'studies')

        # Set the language for the PDF pages
        with translation.override(form.cleaned_data['language']):

            # Create PDF object
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            pdf_buffer = BytesIO()
            pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=A4)

            if group_dogroups:
                pre_enrollments = pre_enrollments.order_by('dogroup', sort_by)
                current_dogroup = None
                for enrollment in pre_enrollments:
                    if current_dogroup != enrollment.dogroup:
                        # Add separator page for dogroup
                        pdf_separator_page(pdf_canvas, str(enrollment.dogroup))
                        current_dogroup = enrollment.dogroup

                    # Add forms to PDF
                    pdf_membership_page(pdf_canvas, enrollment, enrollment.membership_type, signing_date=sign_date)
                    for authorization in enrollment.authorizations.all():
                        pdf_authorization_page(pdf_canvas, (authorization, enrollment), signing_date=sign_date)
            else:
                pre_enrollments = pre_enrollments.order_by(sort_by)
                for enrollment in pre_enrollments:
                    # Add forms to PDF
                    pdf_membership_page(pdf_canvas, enrollment, enrollment.membership_type, signing_date=sign_date)
                    for authorization in enrollment.authorizations.all():
                        pdf_authorization_page(pdf_canvas, (authorization, enrollment), signing_date=sign_date)

            pdf_canvas.save()

        pdf = pdf_buffer.getvalue()
        return HttpResponse(pdf, content_type='application/pdf')



@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def registration_form(request, user, membership):
    from amelie.tools.pdf import pdf_enrollment_form

    buffer = BytesIO()
    person = get_object_or_404(Person, id=user)
    membership = get_object_or_404(Membership, id=membership, member=person)
    pdf_enrollment_form(buffer, person, membership)
    pdf = buffer.getvalue()
    return HttpResponse(pdf, content_type='application/pdf')


@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def membership_form(request, user, membership):
    from amelie.tools.pdf import pdf_membership_form

    buffer = BytesIO()
    person = get_object_or_404(Person, id=user)
    membership = get_object_or_404(Membership, id=membership, member=person)
    pdf_membership_form(buffer, person, membership)
    pdf = buffer.getvalue()
    return HttpResponse(pdf, content_type='application/pdf')


@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def mandate_form(request, mandate):
    from amelie.tools.pdf import pdf_authorization_form

    buffer = BytesIO()
    mandate = get_object_or_404(Authorization, id=mandate)
    pdf_authorization_form(buffer, mandate)
    pdf = buffer.getvalue()
    return HttpResponse(pdf, content_type='application/pdf')


@require_superuser
def registration_check(request):
    if request.method == "POST":
        student_number_form = StudentNumberForm(request.POST)
        if student_number_form.is_valid():
            obj = Student.objects.get(number=student_number_form.cleaned_data["student_number"]).person
            return redirect('members:registration_check_view', id=obj.id, slug=obj.slug)
    else:
        student_number_form = StudentNumberForm()

    return render(request, 'registration_check.html', locals())


@require_superuser
@transaction.atomic
def registration_check_view(request, id, slug):
    obj = get_object_or_404(Person, id=id, slug=slug)
    if request.method == "POST":
        rfid_form = RFIDCardForm(obj, request.POST)
        if rfid_form.is_valid():
            rfid_form.save()
            return redirect('members:registration_check_view', id=obj.id, slug=obj.slug)
    else:
        rfid_form = RFIDCardForm(obj)
    cookie_corner_mandate = obj.has_mandate_activities()
    student_number_form = StudentNumberForm()

    debug = settings.DEBUG

    return render(request, 'registration_check.html', locals())


@require_board
def birthdays(request):
    today_minus_three = timezone.now() - datetime.timedelta(days=3)
    birthdays_list = []
    for date_option in [today_minus_three + datetime.timedelta(x) for x in range(11)]:
        people = Person.objects.members().filter(date_of_birth__day=date_option.day,
                                                 date_of_birth__month=date_option.month)
        for person in people:
            person.becoming_age = person.age(at=date_option)
        birthdays_list.extend(people)

    return render(request, 'birthdays.html', {'birthdays': birthdays_list})


@require_board
def contact_list(request):
    committees = Committee.objects.filter(abolished__isnull=True, category__isnull=False)
    people = Person.objects.all()
    return render(request, 'telephone_list.html', locals())


@require_board
def csv_student_number_primary(request):
    persons = Person.objects.filter(student__studyperiod__study__primary_study=True,
                                    student__number__isnull=False)
    return HttpResponse(",".join(["s%07d" % p.student.number for p in persons if p.is_member()]))


@require_board
def csv_student_number_without_bit(request):
    persons = Person.objects.filter(student__studyperiod__study__primary_study=True,
                                    student__number__isnull=False).exclude(student__studyperiod__study__abbreviation=settings.BIT_BSC_ABBR)
    return HttpResponse(",".join(["s%07d" % p.student.number for p in persons if p.is_member()]))


@require_lid_or_oauth
def picture(request, filename):
    try:
        person = Person.objects.get(picture='pasfoto/%s.jpg' % filename)
    except:
        raise Http404('Picture not found or multiple people are linked to the same picture.')

    if not request.is_board and not request.person == person:
        raise Http404('You do not have access to view this picture.')

    response = HttpResponse(FileWrapper(person.picture), content_type='image/jpeg')
    response['Content-Disposition'] = 'inline; filename=%s.jpg' % filename
    return response


@require_lid_or_oauth
def person_picture(request, id, slug):
    person = get_object_or_404(Person, id=id, slug=slug)

    # Only for the board or the person themselves
    if not request.is_board and not request.person == person:
        return HttpResponseForbidden()

    # Serve file, preferably using Sendfile
    image_file = person.picture
    if image_file:
        return HttpResponseSendfile(path=image_file.path, content_type='image/jpeg')
    else:
        raise Http404('Picture not found')


def _person_info_request_get_body(request, logger=None):
    if logger is None:
        logger = logging.getLogger("amelie.members.views._person_info_request_get_body")

    # Settings for userinfo API must be configured
    if settings.USERINFO_API_CONFIG.get('api_key', None) is None or \
            settings.USERINFO_API_CONFIG.get('allowed_ips', None) is None:
        logger.error("UserInfo API config missing from settings.")
        raise ImproperlyConfigured("UserInfo API config missing from settings.")

    # Must be POST request
    if request.method != "POST":
        logger.error(f"Bad request, request method is {request.method}, not POST.")
        raise BadRequest()

    # Must contain JSON body
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.error(f"Bad request, JSON decoding failed - {e}.")
        raise BadRequest()

    # Must contain 'apiKey' key, and one of the 'iaUsername', 'utUsername' or 'localUsername' keys
    if 'apiKey' not in body or ('iaUsername' not in body and 'utUsername' not in body and 'localUsername' not in body):
        logger.error(f"Bad request, API Key or username key missing.")
        raise BadRequest()

    # API Key must be valid
    api_key = body.pop('apiKey')  # Removes apiKey from the returned body
    if api_key != settings.USERINFO_API_CONFIG['api_key']:
        logger.error(f"Permission denied, provided API key is incorrect.")
        raise PermissionDenied()

    # If given, the 'verify' key should be a boolean value
    if 'verify' in body and not isinstance(body['verify'], bool):
        logger.error("Bad request, verify key was given but was not a boolean value.")
        raise BadRequest()

    # If given, the 'departments' key should be a comma separated string value
    if 'departments' in body and not isinstance(body['departments'], str):
        logger.error("Bad request, departments key was given but was not a comma separated string value.")
        raise BadRequest()

    return body


def _get_ttl_hash(seconds=3600):
    return round(time.time() / seconds)


# noinspection PyUnusedLocal
@lru_cache()
def _person_info_get_person(ia_username=None, ut_username=None, local_username=None, verify=False, departments=None,
                            ttl_hash=None, logger=None):
    if logger is None:
        logger = logging.getLogger("amelie.members.views._person_info_get_person")

    if departments is None:
        departments = []
    else:
        departments = departments.split(",")

    del ttl_hash  # ttl_hash is just to get the lru_cache decorator to keep results for only 1 hour
    person = None
    if ia_username is not None:
        try:
            person = Person.objects.get(account_name=ia_username)
            logger.debug(f"Person found by ia_username {ia_username}: {person}.")
        except Person.DoesNotExist:
            # It could also be an ExtraPerson
            try:
                person = ExtraPerson.objects.get(adname=ia_username)
                logger.debug(f"ExtraPerson found by ia_username {ia_username}: {person}.")
                if not person.is_active():
                    person = None
                    logger.info(f"Account of ExtraPerson {person} is not active (any more), "
                                f"and thus is no info will be returned for username {ia_username}.")
            except ExtraPerson.DoesNotExist:
                logger.info(f"Person or ExtraPerson with ia_username {ia_username} does not exist.")
                person = None
    elif ut_username is not None:
        try:
            if ut_username[0] == 's':
                person = Person.objects.get(student__number=ut_username[1:])
                logger.debug(f"Person found by student ut_username {ut_username}: {person}.")

                if verify and person.membership is not None:
                    # Verify studies of person if department data is present in auth request.
                    logger.debug(f"Verifying study for {person} with departments {departments}.")

                    # Since UT years are from sept-aug and our year is from jul-jun, there are two months overlap.
                    # Never verify users in July or August, as this could allow members who are done studying to get an
                    # extra year as study long.
                    if not person.membership.is_verified() and datetime.date.today().month not in [7, 8]:
                        primary_studies = Study.objects.filter(primary_study=True).values_list('abbreviation',
                                                                                               flat=True)
                        for study in departments:
                            if study in primary_studies:
                                person.membership.verify()
                                break

            elif ut_username[0] == 'm':
                person = Person.objects.get(employee__number=ut_username[1:])
                logger.debug(f"Person found by employee ut_username {ut_username}: {person}.")
            elif ut_username[0] == 'x':
                person = Person.objects.get(ut_external_username=ut_username)
                logger.debug(f"Person found by external ut_username {ut_username}: {person}.")
            else:
                logger.info(f"Cannot find person with invalid ut_username {ut_username}.")
                person = None
        except Person.DoesNotExist:
            logger.info(f"Person with ut_username {ut_username} does not exist.")
            person = None
    elif local_username is not None:
        match = re.match(r'ia(?P<person_id>[0-9]+)', local_username)
        person = None
        if match:
            person_id = int(match.group('person_id'))
            try:
                person = Person.objects.get(pk=person_id)
                logger.debug(f"Person found by local_username {local_username}: {person}.")
            except Person.DoesNotExist:
                logger.info(f"Person with local_username {local_username} does not exist.")
                person = None
        else:
            logger.info(f"Cannot find person with invalid local_username {local_username}.")
            person = None
    else:
        logger.warning(f"Person lookup requested but no IA, UT or local username given?! - "
                       f"Args: ia_username={ia_username}, ut_username={ut_username}, local_username={local_username}, "
                       f"verify={verify}, departments={departments}.")
    return person


@csrf_exempt
def person_userinfo(request):
    """
    Retrieves user info about a person based on either their active member username or UT s- or m-number.
    Used by our authentication platform to determine permissions for external users (UT or social login).

    This endpoint is called whenever a user authenticates to a service via auth.ia that requires IA user details.
    """
    log = logging.getLogger("amelie.members.views.person_userinfo")
    # Verify request and get the JSON body
    body = _person_info_request_get_body(request, logger=log)

    # Access verified. Find the Person associated with the provided username.
    person = _person_info_get_person(
        ia_username=body.get('iaUsername', None), ut_username=body.get('utUsername', None),
        local_username=body.get('localUsername', None), ttl_hash=_get_ttl_hash(), logger=log
    )

    username = body.get('iaUsername', None) or body.get('utUsername', None) or body.get('localUsername', None)

    # If a person was found, return the userinfo that auth.ia needs. Else return an empty object.
    if person is not None and isinstance(person, Person):
        log.info(f"UserInfo retrieved for person {person} using username {username}.")
        email = "{}@{}".format(person.get_adname(), settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN'])
        return HttpJSONResponse({
            'iaUsername': person.get_adname() or None,
            'iaEmail': email if person.get_adname() else None,
            'studentNumber': f"s{person.student.number}" if person.is_student() else None,
            'employeeNumber': f"m{person.employee.number}" if person.is_employee() else None,
            'externalUsername': person.ut_external_username
        })
    elif person is not None and isinstance(person, ExtraPerson):
        log.info(f"UserInfo retrieved for ExtraPerson {person} using username {username}.")
        return HttpJSONResponse({
            'iaUsername': person.get_adname() or None,
            'iaEmail': person.get_email() or None,
            'studentNumber': None,
            'employeeNumber': None,
            'externalUsername': None
        })
    else:
        log.info(f"UserInfo not found for user iaUsername={body.get('iaUsername', None)}, "
                 f"utUsername={body.get('utUsername', None)}, localUsername={body.get('localUsername', None)}.")
        return HttpJSONResponse({})


@csrf_exempt
def person_groupinfo(request):
    """
    Retrieves group info about a person based on either their active member username or UT s- or m-number.
    Used by our authentication platform to determine permissions for external users (UT or social login).

    This also verifies studies if requested, because the UT department info will be passed to this endpoint in the
    body if it was received by the authentication platform. This endpoint is called when a user logs in with an
    external account (UT, Google, GitHub, etc.).
    """
    log = logging.getLogger("amelie.members.views.person_groupinfo")
    # Verify request and get the JSON body
    body = _person_info_request_get_body(request, logger=log)

    # Access verified. Find the Person associated with the provided username.
    person = _person_info_get_person(
        ia_username=body.get('iaUsername', None), ut_username=body.get('utUsername', None),
        local_username=body.get('localUsername', None), verify=body.get('verify', False),
        departments=body.get('departments', None), ttl_hash=_get_ttl_hash(), logger=log
    )

    username = body.get('iaUsername', None) or body.get('utUsername', None) or body.get('localUsername', None)

    # If a person was found, return the userinfo that auth.ia needs. Else return an empty object.
    if person is not None:
        mp = Mapping.find(person)
        if mp is not None:
            log.info(f"GroupInfo retrieved for person {person} (cid: {mp.id}) using username {username}.")
            return HttpJSONResponse({
                "groups": [g.adname for g in mp.all_groups('ad') if g.is_group_active() and g.adname]
            })
        else:
            log.info(f"GroupInfo found no groups for username {username} - User has no mapping.")
            return HttpJSONResponse({"groups": []})
    log.info(f"GroupInfo not found for username(s) ia={body.get('iaUsername', None)} "
             f"ut={body.get('utUsername', None)} local={body.get('localUsername', None)}.")
    return HttpJSONResponse({})


@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_send_link_code(request, person_id):
    person = get_object_or_404(Person, id=person_id)
    link_code = get_oauth_link_code(person)
    send_oauth_link_code_email(request, person, link_code)
    name = person.incomplete_name()
    messages.success(request, _(f"OAuth link code and instructions were sent to {name}."))
    return HttpResponseRedirect(person.get_absolute_url())


@require_board
def books_list(request):
    STUDIES_BIT = (settings.BIT_BSC_ABBR, settings.BIT_MSC_ABBR)
    bit_students = Person.objects.members().filter(
        student__studyperiod__study__abbreviation__in=STUDIES_BIT,
        student__number__isnull=False).values_list('student__number', flat=True).order_by('student__number')
    non_bit_students = Person.objects.members().exclude(student__studyperiod__study__abbreviation__in=STUDIES_BIT).filter(
        student__number__isnull=False).values_list('student__number', flat=True).order_by('student__number')

    student_numbers_bit = ["s%07d" % p for p in bit_students]
    student_numbers_other = ["s%07d" % p for p in non_bit_students]

    return render(request, 'books_list.html', {'student_numbers_bit': student_numbers_bit,
                                               'student_numbers_other': student_numbers_other, })


class PaymentDeleteView(RequireBoardMixin, DeleteMessageMixin, DeleteView):
    model = Payment
    template_name = "members/payment_confirm_delete.html"

    def get_object(self, queryset=None):
        payment = super(PaymentDeleteView, self).get_object()
        # You are not allowed to delete 'zero'-memberships manually
        if payment.amount == 0.0:
            raise PermissionDenied(_("You are not allowed to manually delete the payments of free memberships."))
        # You are not allowed to delete payments that are (currently) debited manually
        if payment.membership.contributiontransaction_set.count() > 0:
            raise PermissionDenied(_("You are not allowed to delete payments that are already (being) debited."))
        return payment

    def get_delete_message(self):
        return _('Payment %(object)s has been removed' % {'object': self.get_object()})

    def get_success_url(self):
        return self.object.membership.member.get_absolute_url()


class DoGroupTreeView(TemplateView):
    template_name = "dogroups.html"


# TODO: Add caching to this view! This cache can be kept for a month of so.
class DoGroupTreeViewData(View):

    def get(self, request, *args, **kwargs):
        # Create a datastructure that maps connects generations based on parents and children
        generation_objects = DogroupGeneration.objects.select_related('dogroup').prefetch_related(
            'studyperiod_set').all().order_by('dogroup', 'generation')

        # A data structure
        generations = dict()

        # Aggregates all the years that have had dogroups
        years = set()
        for generation in generation_objects:
            years.add(generation.generation)
            prev = set()
            for parent in generation.parents.all():
                if parent.is_student():
                    parent_prev_dogroups = parent.student.studyperiod_set.filter(dogroup__isnull=False,
                                                                                 dogroup__generation__lt=generation.generation).order_by(
                        'dogroup__generation')
                    if parent_prev_dogroups.exists():
                        prev.add(parent_prev_dogroups.last().dogroup)
            generations[generation] = prev

        dogroups = dict()
        for dogroup in Dogroup.objects.all():
            dogroups[str(dogroup)] = {}
        for generation in generations.keys():
            dogroups[str(generation.dogroup)][generation.generation] = {
                "id": generation.id,
                "parents": [{"id": p.id} for p in generations[generation]],
                "color": generation.color,
            }

        data = {
            "years": sorted(list(years)),
            "dogroups": list(dogroups.keys()),
            "data": dogroups,
        }
        return JsonResponse(data)

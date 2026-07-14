import logging
from datetime import date

import re

from django.conf import settings
from django.forms.models import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.views.generic import FormView, TemplateView
from documenso_sdk import DocumensoError

from amelie.members.forms import CommitteeForm, FunctionForm, MembershipEndForm, MembershipForm, \
    MandateEndForm, MandateForm, EmployeeForm, PersonPaymentForm, PersonStudyForm, PersonPreferencesForm, \
    SaveNewFirstModelFormSet, StudentForm, SignatureRequestForm
from amelie.members.models import Payment, Committee, Function, Membership, Employee, PaymentType, Person, Student, \
    StudyPeriod, Preference, PreferenceCategory
from amelie.members.query_views import filter_member_list_public
from amelie.personal_tab.models import Authorization
from amelie.personal_tab.pos_views import require_cookie_corner_pos
from amelie.tools.decorators import require_ajax, require_board, require_actief, require_committee
from amelie.tools.mixins import RequireCommitteeMixin


def person_data(request, obj, type, form_type, view_template=None, edit_template=None, *args, **kwargs):
    if not view_template:
        view_template = "person_%s.html" % type
    if not edit_template:
        edit_template = "person_edit_%s.html" % type
    if request.method == "GET":
        form = form_type(instance=obj)
        ctx = {'form': form, 'obj': obj, }
        ctx.update(kwargs)

        return render(request, view_template if 'original' in request.GET else edit_template, ctx)
    elif request.method == "POST":
        form = form_type(data=request.POST, files=request.FILES, instance=obj)
        ctx = {'form': form, 'obj': obj, }
        ctx.update(kwargs)
        if form.is_valid():
            obj = form.save()
            resp = render(request, view_template, ctx)
            resp["X-Success"] = True
            return resp
        else:
            return render(request, edit_template, ctx)


@require_ajax
@require_board
def person_employee(request, id):
    obj = get_object_or_404(Person, id=id)
    view_template = "person_employee.html"
    edit_template = "person_edit_employee.html"
    remove = request.POST.get('remove', False)
    if request.method == "GET":
        form = EmployeeForm()
        try:
            form = EmployeeForm(instance=obj.employee)
        except:
            pass

        return render(request, view_template if 'original' in request.GET else edit_template, locals())
    elif request.method == "POST":
        try:
            if remove and obj.employee:
                obj.employee.delete()
                obj = get_object_or_404(Person, id=id)
                resp = render(request, view_template, locals())
                resp["X-Success"] = True
                return resp
        except Employee.DoesNotExist:
            pass
        else:
            form = EmployeeForm(request.POST)
            try:
                form = EmployeeForm(request.POST, instance=obj.employee)
            except Employee.DoesNotExist:
                pass
            if form.is_valid():
                employee = form.save(commit=False)
                employee.person = obj
                employee.save()
                form.save_m2m()
                resp = render(request, view_template, locals())
                resp["X-Success"] = True
                return resp
            else:
                return render(request, edit_template, locals())


@require_ajax
@require_board
def person_preferences(request, id):
    obj = get_object_or_404(Person, id=id)
    preference_categories = PreferenceCategory.objects.all()
    forms = []

    for category in PreferenceCategory.objects.all():
        preferences = Preference.objects.filter(category=category)
        id_field = '%s_id_%s' % (slugify(category.name), '%s')
        forms.append((
            category.name,
            PersonPreferencesForm(preferences_set=preferences, instance=obj, auto_id=id_field)
        ))

    return person_data(request, obj, 'preferences', PersonPreferencesForm, preference_categories=preference_categories,
                       forms=forms)


@require_ajax
@require_board
def person_study_new(request, id):
    obj = get_object_or_404(Person, id=id)
    return person_data(request, obj, 'studyperiod', PersonStudyForm)


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_payments(request, id, membership):
    obj = get_object_or_404(Person, id=id)
    membership = get_object_or_404(Membership, id=membership)
    if request.method == "GET":
        if 'original' in request.GET:
            return render(request, "person_membership.html", locals())
        form = PersonPaymentForm()
        return render(request, "person_payment.html", locals())
    elif request.method == "POST":
        form = PersonPaymentForm(request.POST)
        if form.is_valid():
            payment = Payment(membership=membership, payment_type=form.cleaned_data['method'],
                               amount=membership.type.price, date=form.cleaned_data["date"])
            payment.save()
            return render(request, "person_membership.html", locals())
        else:
            response = render(request, "person_payment.html", locals())
            return response


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_membership(request, id, option=None):
    obj = get_object_or_404(Person, id=id)
    return render(request, "person_membership.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_membership_new(request, id):
    obj = get_object_or_404(Person, id=id)
    if request.method == "POST":
        form = MembershipForm(request.POST)
        if form.is_valid():
            membership = form.save(commit=False)
            membership.member = obj
            membership.save()
            return render(request, "person_membership.html", locals())
        else:
            response = render(request, "person_new_membership.html", locals())
            return response
    else:
        form = MembershipForm()
        return render(request, "person_new_membership.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_membership_end(request, id):
    obj = get_object_or_404(Person, id=id)
    membership = obj.membership_set.latest('year', 'pk')
    if request.method == "POST":
        form = MembershipEndForm(request.POST, instance=membership)
        if form.is_valid():
            if form.cleaned_data['payment_needed'] == False and not Payment.objects.filter(membership=membership).exists():
                # If payment is not needed and payment does not exist yet, create one
                # PaymentType is 10: "Voortijdige beëindiging, betaling niet noodzakelijk."
                Payment.objects.create(membership=membership, payment_type=PaymentType.objects.get(pk=10), amount=membership.type.price, date=form.cleaned_data['ended'])
            form.save()
            return render(request, "person_membership.html", locals())
        else:
            response = render(request, "person_end_membership.html", locals())
            return response
    else:
        form = MembershipEndForm(instance=membership)
        return render(request, "person_end_membership.html", locals())


class MembershipSignatureView(RequireCommitteeMixin, FormView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    form_class = SignatureRequestForm
    template_name = "person_membership_sign.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['person'] = get_object_or_404(Person, id=self.kwargs['person_id'])
        context['membership'] = get_object_or_404(Membership, id=self.kwargs['membership_id'], member=context['person'])
        return context

    def form_valid(self, form):
        """
        If the form is valid, send the form to Documenso for signing, and then
        render the regular membership section with a success message option.
        """
        person = get_object_or_404(Person, id=self.kwargs['person_id'])
        membership = get_object_or_404(Membership, id=self.kwargs['membership_id'], member=person)
        try:
            membership.send_signature_request()
            return person_membership(self.request, self.kwargs['person_id'], option="sign_request_sent")
        except DocumensoError as e:
            logging.exception(
                f"Failed to send membership signature request for Person#{person.pk}, Membership#{membership.pk}",
                exc_info=e
            )
            return person_membership(self.request, self.kwargs['person_id'], option="sign_request_error")


class MembershipRetrieveSignedDocumentView(RequireCommitteeMixin, TemplateView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_membership_retrieve_signed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['person'] = get_object_or_404(Person, id=self.kwargs['person_id'])
        membership = get_object_or_404(Membership, id=self.kwargs['membership_id'], member=context['person'])
        context['membership'] = membership
        try:
            membership.process_signed_document()
            context['success'] = True
        except (ValueError, DocumensoError) as e:
            context['success'] = False
            context['error_msg'] = str(e)
        return context


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate(request, id, option=None):
    obj = get_object_or_404(Person, id=id)
    return render(request, "person_mandate.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate_new(request, id):
    obj = get_object_or_404(Person, id=id)
    if request.method == "POST":
        form = MandateForm(request.POST)
        if form.is_valid():
            mandate: Authorization = form.save(commit=False)
            mandate.person = obj
            mandate.save()
            if form.cleaned_data.get('send_signature_request'):
                mandate.send_signature_request()  # Send signature request for the new mandate
                return person_mandate(request, id=id, option="added_and_sign_request_sent")
            return person_mandate(request, id=id, option="added")
        else:
            response = render(request, "person_new_mandate.html", locals())
            return response
    else:
        form = MandateForm(initial={"start_date": date.today(),
                                    "account_holder_name": obj.initials_last_name()})
        return render(request, "person_new_mandate.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate_activate(request, id, mandate):
    obj = get_object_or_404(Person, id=id)
    mandate = get_object_or_404(Authorization, id=mandate, person=obj, end_date__isnull=True, is_signed=False)

    # If there is already an active mandate of this type, we cannot activate this one
    existing_mandates_of_type = obj.authorization_set.filter(is_signed=True, end_date__isnull=True, authorization_type=mandate.authorization_type)
    if existing_mandates_of_type.exists():
        return render(request, "person_existing_mandate.html", locals())

    elif request.method == "POST":
        if 'activate' in request.POST:
            mandate.is_signed = True
            mandate.save()
        return render(request, "person_mandate.html", locals())
    else:
        return render(request, "person_activate_mandate.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate_end(request, id, mandate):
    obj = get_object_or_404(Person, id=id)
    mandate = get_object_or_404(Authorization, id=mandate)
    if mandate.end_date:
        # Mandate is already terminated, do nothing and just give back the mandate details
        # This prevents 'double termination', which would overwrite the original end date of the mandate.
        return render(request, "person_mandate.html", locals())
    if request.method == "POST":
        form = MandateEndForm(request.POST, instance=mandate)
        if form.is_valid():
            form.save()
            return render(request, "person_mandate.html", locals())
        else:
            response = render(request, "person_end_mandate.html", locals())
            return response
    else:
        form = MandateEndForm(instance=mandate, initial={'end_date': date.today()})
        return render(request, "person_end_mandate.html", locals())

class MandateSignatureView(RequireCommitteeMixin, FormView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    form_class = SignatureRequestForm
    template_name = "person_mandate_sign.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['person'] = get_object_or_404(Person, id=self.kwargs['person_id'])
        context['mandate'] = get_object_or_404(Authorization, id=self.kwargs['mandate_id'])
        return context

    def form_valid(self, form):
        """
        If the form is valid, send the form to Documenso for signing, and then
        render the regular membership section with a success message option.
        """
        person = get_object_or_404(Person, id=self.kwargs['person_id'])
        mandate = get_object_or_404(Authorization, id=self.kwargs['mandate_id'])
        try:
            mandate.send_signature_request()
            return person_mandate(self.request, id=self.kwargs['person_id'], option="sign_request_sent")
        except DocumensoError as e:
            logging.exception(
                f"Failed to send mandate signature request for Person#{person.pk}, Authorization#{mandate.pk}",
                exc_info=e
            )
            return person_mandate(self.request, id=self.kwargs['person_id'], option="sign_request_error")


class MandateRetrieveSignedDocumentView(RequireCommitteeMixin, TemplateView):
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    template_name = "person_mandate_retrieve_signed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['person'] = get_object_or_404(Person, id=self.kwargs['person_id'])
        mandate = get_object_or_404(Authorization, id=self.kwargs['mandate_id'])
        context['mandate'] = mandate
        try:
            mandate.process_signed_document()
            context['success'] = True
        except (ValueError, DocumensoError) as e:
            context['success'] = False
            context['error_msg'] = str(e)
        return context


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate_edit(request, id, mandate):
    obj = get_object_or_404(Person, id=id)
    mandate = get_object_or_404(Authorization, id=mandate, person=obj,
                                end_date__isnull=True, is_signed=False)
    if request.method == "POST":
        form = MandateForm(request.POST, instance=mandate)
        if form.is_valid():
            mandate = form.save(commit=False)
            mandate.person = obj
            mandate.save()
            return render(request, "person_mandate.html", locals())
        else:
            response = render(request, "person_edit_mandate.html", locals())
            return response
    else:
        form = MandateForm(instance=mandate)
        return render(request, "person_edit_mandate.html", locals())


@require_ajax
@require_committee(settings.ROOM_DUTY_ABBREVIATION)
def person_mandate_delete(request, id, mandate):
    obj = get_object_or_404(Person, id=id)
    mandate = get_object_or_404(Authorization, id=mandate, person=obj,
                                end_date__isnull=True, is_signed=False)
    if request.method == "POST":
        if 'delete' in request.POST:
            mandate.delete()
        return render(request, "person_mandate.html", locals())
    else:
        return render(request, "person_delete_mandate.html", locals())


@require_ajax
@require_board
def person_functions(request, id):
    obj = get_object_or_404(Person, id=id)

    if 'original' in request.GET:
        return render(request, "person_functions.html", locals())

    FunctionFormSet = inlineformset_factory(Person, Function, form=FunctionForm, extra=1, can_delete=False,
                                            formset=SaveNewFirstModelFormSet)
    formset = FunctionFormSet(instance=obj)

    if request.method == "POST":
        formset = FunctionFormSet(request.POST, instance=obj)
        if formset.is_valid():
            formset.save()
            obj = get_object_or_404(Person, id=id)
            return render(request, "person_functions.html", locals())

    return render(request, "person_edit_functions.html", locals())


@require_ajax
@require_board
def person_study(request, id):
    obj = get_object_or_404(Person, id=id)

    if 'original' in request.GET:
        return render(request, "person_study.html", locals())

    StudyperiodFormSet = inlineformset_factory(Student, StudyPeriod, extra=1, can_delete=False,
                                               fields=['study', 'begin', 'end', 'graduated', 'dogroup'])
    form = StudentForm()
    formset = StudyperiodFormSet()
    try:
        form = StudentForm(instance=obj.student)
        formset = StudyperiodFormSet(instance=obj.student)
    except:
        pass

    if request.method == "POST":
        try:
            form = StudentForm(request.POST, instance=obj.student)
            formset = StudyperiodFormSet(request.POST, instance=obj.student)
        except:
            student = Student(person=obj)
            form = StudentForm(request.POST, instance=student)
            if form.is_valid():
                student = form.save()
            formset = StudyperiodFormSet(request.POST, instance=student)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            obj = get_object_or_404(Person, id=id)
            return render(request, "person_study.html", locals())

    return render(request, "person_edit_study.html", locals())


@require_ajax
@require_board
def committee_data(request, id):
    # TODO: Check if this view is used anywhere and remove it and its templates if it isn't - albertskja 24-04-2018
    obj = get_object_or_404(Committee, id=id)
    is_board = request.user.is_staff

    if 'original' in request.GET:
        return render(request, "committee_data.html", locals())

    form = CommitteeForm(instance=obj)

    if request.method == "POST":
        form = CommitteeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            obj = get_object_or_404(Committee, id=id)
            return render(request, "committee_data.html", locals())

    return render(request, "committee_edit_data.html", locals())


SEARCH_REGEX = re.compile(r'^([^()]+)(?:\([^()]\) *)?([^()]+)?$')


@require_ajax
@require_actief
def autocomplete_names(request):
    if 'q' in request.GET:
        search = request.GET['q']
        match = SEARCH_REGEX.fullmatch(search)
        if match and match.lastindex == 2:
            search = ''.join(match.groups())
        return JsonResponse(
            {person.id: person.full_name() for person in filter_member_list_public({'search': search}, 5)})
    return JsonResponse({'names': None})


# Endpoint for the cookie corner for autocompletion of members if board is registering an external card
@require_ajax
@require_cookie_corner_pos
def autocomplete_names_cookie_corner(request):
    if 'q' in request.GET:
        search = request.GET['q']
        match = SEARCH_REGEX.fullmatch(search)
        if match and match.lastindex == 2:
            search = ''.join(match.groups())
        return JsonResponse(
            {person.id: person.full_name() for person in filter_member_list_public({'search': search}, 5)})
    return JsonResponse({'names': None})

from datetime import date

import re

from django.contrib import messages
from django.forms.models import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.defaultfilters import slugify

from amelie.members.forms import CommitteeForm, FunctionForm, MembershipEndForm, MembershipForm, \
    MandateEndForm, MandateForm, EmployeeForm, PersonPaymentForm, PersonStudyForm, PersonPreferencesForm, \
    SaveNewFirstModelFormSet, StudentForm
from amelie.members.models import Payment, Committee, Function, Membership, Employee, Person, Student, \
    StudyPeriod, Preference, PreferenceCategory
from amelie.members.query_views import filter_member_list_public
from amelie.personal_tab.models import Authorization
from amelie.personal_tab.pos_views import require_cookie_corner_pos
from amelie.tools.decorators import require_ajax, require_board, require_actief


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
@require_board
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
@require_board
def person_membership(request, id, option=None):
    obj = get_object_or_404(Person, id=id)
    return render(request, "person_membership.html", locals())


@require_ajax
@require_board
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
@require_board
def person_membership_end(request, id):
    obj = get_object_or_404(Person, id=id)
    if request.method == "POST":
        form = MembershipEndForm(request.POST, instance=obj.membership_set.latest('year'))
        if form.is_valid():
            form.save()
            return render(request, "person_membership.html", locals())
        else:
            response = render(request, "person_end_membership.html", locals())
            return response
    else:
        form = MembershipEndForm(instance=obj.membership_set.latest('year'))
        return render(request, "person_end_membership.html", locals())


@require_ajax
@require_board
def person_mandate(request, id):
    obj = get_object_or_404(Person, id=id)
    return render(request, "person_mandate.html", locals())


@require_ajax
@require_board
def person_mandate_new(request, id):
    obj = get_object_or_404(Person, id=id)
    if request.method == "POST":
        form = MandateForm(request.POST)
        if form.is_valid():
            mandate = form.save(commit=False)
            mandate.person = obj
            mandate.save()
            return render(request, "person_mandate.html", locals())
        else:
            response = render(request, "person_new_mandate.html", locals())
            return response
    else:
        form = MandateForm(initial={"start_date": date.today(),
                                    "account_holder_name": obj.initials_last_name()})
        return render(request, "person_new_mandate.html", locals())


@require_ajax
@require_board
def person_mandate_activate(request, id, mandate):
    obj = get_object_or_404(Person, id=id)
    mandate = get_object_or_404(Authorization, id=mandate, person=obj,
                                end_date__isnull=True, is_signed=False)
    if request.method == "POST":
        if 'activate' in request.POST:
            mandate.is_signed = True
            mandate.save()
        return render(request, "person_mandate.html", locals())
    else:
        return render(request, "person_activate_mandate.html", locals())


@require_ajax
@require_board
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

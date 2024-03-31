import shutil

import base64
import datetime
import email
import logging
import os
import re
import csv
from pathlib import Path

from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.urls import reverse, reverse_lazy
from django.db import transaction
from django.db.models import F, Q, Count, Sum
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.utils import translation
from urllib.parse import quote
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

from amelie.activities.forms import ActivityForm, PaymentForm, PhotoUploadForm, \
    EnrollmentoptionCheckboxAnswerForm, EnrollmentoptionCheckboxForm, EnrollmentoptionFoodAnswerForm, \
    EnrollmentoptionFoodForm, EnrollmentoptionQuestionAnswerForm, EnrollmentoptionQuestionForm, \
    EventDeskActivityMatchForm, EnrollmentoptionNumericForm, EnrollmentoptionNumericAnswerForm, PhotoFileUploadForm
from amelie.activities.mail import activity_send_enrollmentmail, activity_send_on_waiting_listmail, activity_send_cancellationmail, activity_send_cashrefundmail
from amelie.activities.models import Activity, DishPrice, Enrollmentoption, EnrollmentoptionCheckbox, \
    EnrollmentoptionCheckboxAnswer, EnrollmentoptionFood, EnrollmentoptionFoodAnswer, EnrollmentoptionQuestion, \
    EnrollmentoptionQuestionAnswer, EventDeskRegistrationMessage, Restaurant, EnrollmentoptionNumeric, \
    EnrollmentoptionNumericAnswer
from amelie.activities.tasks import save_photos
from amelie.activities.utils import check_enrollment_allowed, check_unenrollment_allowed, update_waiting_list
from amelie.claudia.google import GoogleSuiteAPI
from amelie.files.models import Attachment
from amelie.calendar.models import Participation, Event
from amelie.members.forms import PersonSearchForm
from amelie.members.models import Person, Photographer
from amelie.members.query_forms import MailingForm
from amelie.tools import amelie_messages, types
from amelie.tools.decorators import require_actief, require_lid, require_committee, require_board
from amelie.tools.forms import PeriodForm, ExportForm, PeriodKeywordForm
from amelie.tools.calendar import ical_calendar
from amelie.tools.mixins import RequireActiveMemberMixin, DeleteMessageMixin, PassesTestMixin, RequireBoardMixin, \
    RequireCommitteeMixin
from amelie.tools.paginator import RangedPaginator

logger = logging.getLogger(__name__)

ENROLLMENTOPTION_ANSWER_TYPES = {
    EnrollmentoptionQuestion: EnrollmentoptionQuestionAnswer,
    EnrollmentoptionCheckbox: EnrollmentoptionCheckboxAnswer,
    EnrollmentoptionFood: EnrollmentoptionFoodAnswer,
    EnrollmentoptionNumeric: EnrollmentoptionNumericAnswer,
}

ENROLLMENTOPTIONANSWER_FORM_TYPES = {
    EnrollmentoptionQuestion: EnrollmentoptionQuestionAnswerForm,
    EnrollmentoptionCheckbox: EnrollmentoptionCheckboxAnswerForm,
    EnrollmentoptionFood: EnrollmentoptionFoodAnswerForm,
    EnrollmentoptionNumeric: EnrollmentoptionNumericAnswerForm,
}

ENROLLMENTOPTION_FORM_TYPES = {
    EnrollmentoptionQuestion: EnrollmentoptionQuestionForm,
    EnrollmentoptionCheckbox: EnrollmentoptionCheckboxForm,
    EnrollmentoptionFood: EnrollmentoptionFoodForm,
    EnrollmentoptionNumeric: EnrollmentoptionNumericForm,
}


def activities_ics(request, lang=None):
    """
    ical-feed for activities.
    """
    if lang is not None:
        translation.activate(lang)

    act = Activity.objects \
        .filter_public(request) \
        .filter(begin__gte=timezone.now() - datetime.timedelta(100)) \
        .order_by('begin')

    ical_contents = ical_calendar(_('Events of Inter-Actief'), act,
                                  max_duration_before_split=datetime.timedelta(days=5))

    return HttpResponse(ical_contents, content_type='text/calendar; charset=UTF-8')


def activity_ics(request, pk):
    """
    Returns the ical for an activity.
    """
    activity = get_object_or_404(Activity, pk=pk)
    if not activity.public and not request.user.is_authenticated:
        raise PermissionDenied

    resp = HttpResponse(content_type='text/calendar; charset=UTF-8')
    resp.write(ical_calendar(_(activity.summary), [activity, ]))

    return resp


def activities(request):
    """
    Gives an overview of all upcoming activities and recent past activities.
    """
    activities = Event.objects.filter_public(request)
    old_activities = list(activities.filter(end__lt=timezone.now()))[-10:]
    new_activities = list(activities.filter(end__gte=timezone.now()))

    old_activities = [a.as_leaf_class() for a in old_activities]
    new_activities = [a.as_leaf_class() for a in new_activities]
    only_open_enrollments = 'openEnrollments' in request.GET

    return render(request, "activity_list.html", locals())


def activities_old(request):
    """
    Gives an overview of past activities.

    You can filter on a date and on a few keywords.
    """
    form = PeriodKeywordForm(to_date_required=False, keywords_required=False, data=request.GET or None)

    if form.is_valid():
        keywords = form.cleaned_data['keywords']
        start_date = form.cleaned_data['from_date']
        end_date = form.cleaned_data['to_date'] or timezone.now()
    else:
        keywords = ""
        start_date = form.fields['from_date'].initial
        end_date = form.fields['to_date'].initial

    # Convert dates to datetimes
    start_datetime = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time()))
    end_datetime = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time()))

    # Filter for activities in tim  range
    old_activities = Activity.objects.filter_public(request).filter(end__range=(start_datetime, end_datetime)) \
        .order_by('-end')

    if 'keywords' in form.data.keys():
        # Filter for activities with keyword
        old_activities = old_activities.filter(Q(summary_en__icontains=keywords) |
                                               Q(description_en__icontains=keywords) |
                                               Q(summary_nl__icontains=keywords) |
                                               Q(description_nl__icontains=keywords))

    return render(request, "activity_old.html", {
        'form': form,
        'old_activities': old_activities,
    })


def activity(request, pk, deanonymise=False):
    """
    Shows an activity.
    """
    activity = get_object_or_404(Activity, pk=pk)
    if not activity.public and not request.user.is_authenticated:
        raise PermissionDenied

    if activity.participants:
        number_participants = activity.participants.count()
        number_confirmed_participants = activity.confirmed_participants.count()
        number_waiting_participants = activity.waiting_participants.count()
    if request.user.is_authenticated and hasattr(request, 'person'):
        can_edit = activity.can_edit(request.person)
    else:
        can_edit = False

    import icalendar
    evt = icalendar.Event()
    evt.add('dtstart', activity.begin)
    evt.add('dtend', activity.end)
    evt.add('summary', activity.summary)

    current_time = timezone.now()

    only_show_underage = hasattr(request, 'is_board') and request.is_board and (request.GET.get('underage') == "True")

    # Extra check to make sure that no sensitive data will be leaked
    if can_edit:
        restaurants = Restaurant.objects \
            .filter(enrollmentoptionfood__activity=activity,
                    dish__dishprice__enrollmentoptionfoodanswer__enrollmentoption__activity=activity) \
            .annotate(amount=Count('enrollmentoptionfood__activity'),
                      total_price=Sum('dish__dishprice__price')) \
            .distinct()
        for restaurant in restaurants:
            restaurant.dishes = DishPrice.objects \
                .filter(enrollmentoptionfoodanswer__enrollmentoption__activity=activity,
                        dish__restaurant=restaurant, enrollmentoptionfoodanswer__enrollment__waiting_list=False) \
                .annotate(amount=Count('enrollmentoptionfoodanswer',
                                       filter=Q(enrollmentoptionfoodanswer__enrollment__waiting_list=False)),
                          total_price=Sum('price',
                                          filter=Q(enrollmentoptionfoodanswer__enrollment__waiting_list=False)))
        total_price = sum([(restaurant.dishes.aggregate(Sum('total_price')).get(
            'total_price__sum')) if restaurant.dishes.aggregate(Sum('total_price')).get(
            'total_price__sum') is not None else 0 for restaurant in restaurants])
        total_amount = sum(
            [restaurant.dishes.aggregate(Sum('amount')).get('amount__sum') for restaurant in restaurants])

    can_view_photos = activity.photos.filter_public(request).count() > 0
    obj = activity  # Template laziness

    # Sorted set of participations that are used to show the enrollments
    participation_set = activity.participation_set.order_by('added_on')

    if only_show_underage:
        confirmed_participation_set = [x for x in
                                       activity.participation_set.filter(waiting_list=False).order_by('added_on') if
                                       x.person.age(at=activity.begin) < 18]
        confirmed_participation_set_turns_18_during_event = [x for x in confirmed_participation_set if
                                                             x.person.age(at=activity.end) >= 18]
    else:
        confirmed_participation_set = activity.participation_set.filter(waiting_list=False).order_by('added_on')

    waiting_participation_set = activity.participation_set.filter(waiting_list=True).order_by('added_on')

    if hasattr(request, 'person') and waiting_participation_set.filter(person=request.person).exists():
        added_on = waiting_participation_set.get(person=request.person).added_on
        number_on_waiting_list = waiting_participation_set.filter(added_on__lte=added_on).count()

    if hasattr(request, 'person') and (request.person in obj.participants.all()):
        participation = Participation.objects.get(person=request.person, event=activity)

    has_enrollment_options = activity.has_enrollmentoptions()

    # Data Export form for GDPR compliance.
    export_form = ExportForm()
    export_form.fields['export_details'].initial = str(obj)

    # Enable opengraph on this page
    metadata_enable_opengraph = True

    return render(request, "activity.html", locals())


def activity_random_photo(request, pk, *args, **kwargs):
    """ Returns a random photo of a specific activity. """
    act = get_object_or_404(Activity, pk=pk)
    photo = act.random_photo(only_public=not hasattr(request, 'person'))

    # Generate a JSON response
    if photo:
        return photo.to_http_response(format='medium', response='json')

    # No photo
    raise Http404(_('No photo'))


@require_board
@transaction.atomic
def activity_delete(request, pk):
    """
    Deletes an activity.

    Activities may only be removed when these do not have any remaining enrollments left.

    Asks for a confirmation.
    """
    obj = get_object_or_404(Activity, pk=pk)
    if not obj.can_edit(request.person):
        raise PermissionDenied

    if request.POST:
        if 'yes' in request.POST:
            # Undo transactions and remove participations
            from amelie.personal_tab import transactions
            for participation in obj.participation_set.all():
                transactions.participation_transaction(participation, "Cancelled event", cancel=True,
                                                       added_by=request.person)
                # Remove the participation
                participation.delete()

            obj.delete()
            return redirect(reverse('activities:activities'))
        elif 'no' in request.POST:
            return redirect(obj)

    return render(request, "activity_confirm_delete.html", locals())


@require_board  # Cancelling an activity is only allowed by the board due to possible transactions that should be undone.
@transaction.atomic
def activity_cancel(request, pk):
    """
    Cancels or re-publishes an activity (depending on the current status of this event).

    Events may only be cancelled if they have not yet started.

    In the case of cancellation, this function removes all enrollments (and closes the option to enroll) and undoes the corresponding transactions.
    In the case of re-publishing, the event name will be reverted to its original name and enrollments will be re-openend.

    Asks for a confirmation.
    """
    obj = get_object_or_404(Activity, pk=pk)

    # If the event is already cancelled, immediately re-publish it without any confirmation screen.
    if obj.cancelled:
        obj.cancelled = False
        obj.save()
        messages.success(request, _(f"{obj} has been successfully re-opened. Please note that all previous enrollments are not added again and that enrollments will have to be manually re-opened."))
        return redirect(obj)

    if request.POST:
        if 'yes' in request.POST:

            if obj.begin < timezone.now():
                messages.error(_(f'We were unable to cancel {obj}, since it has already started.'))
                return redirect(obj)
            else:
                activity_send_cancellationmail(obj.participation_set.all(), obj, request)

                # Send an email to the treasurer if people have paid in cash.
                # This email contains the names and amount paid by each person.
                if obj.participation_set.filter(payment_method=Participation.PaymentMethodChoices.CASH, cash_payment_made=True).exists():
                    activity_send_cashrefundmail(obj.participation_set.filter(payment_method=Participation.PaymentMethodChoices.CASH, cash_payment_made=True).all(), obj, request)

                # Undo transactions and remove participations
                from amelie.personal_tab import transactions
                for participation in obj.participation_set.all():
                    if participation.payment_method == Participation.PaymentMethodChoices.AUTHORIZATION:
                        transactions.participation_transaction(participation, f"Cancelled {obj}", cancel=True, added_by=request.person)
                    # Remove the participation
                    participation.delete()

                obj.cancelled = True
                obj.enrollment = False
                obj.save()
                messages.success(request, _(f"{obj} was cancelled successfully."))
        return redirect(obj)

    return render(request, "activity_confirm_cancellation.html", locals())


@require_POST
@require_lid
@transaction.atomic
def activity_enrollment(request, pk):
    """
    Enrolls the currently logged in person for this activity.

    Redirect to the elaborate form if more data is needed,
    or if there are any costs associated with the activity.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    obj = get_object_or_404(Activity.objects.select_for_update(), pk=pk)
    enrollment_full = obj.enrollment_full()

    if not check_enrollment_allowed(request, obj):
        # The method check_enrollment_allowed makes sure that something is in django messages if the enrollment is not allowed.
        return redirect(obj)

    # Check whether the user needs to be redirected to an enrollment form
    if obj.enrollmentoption_set.count() == 0 and obj.price == 0:
        # Simple enrollment: no questions or costs
        participation = Participation(person=request.person, event=obj,
                                      payment_method=Participation.PaymentMethodChoices.NONE, added_by=request.person,
                                      waiting_list=enrollment_full)
        participation.save()

        # Send mail if preference asks for it
        if request.person.has_preference(name='mail_enrollment'):
            if not enrollment_full:
                activity_send_enrollmentmail(participation)
                messages.success(request,
                                 _('You are now enrolled for {activity}.').format(
                                     activity=obj,
                                 ))
            else:
                activity_send_on_waiting_listmail(participation)
                messages.success(request,
                                 _('You are now on the waiting list for {activity}.').format(
                                     activity=obj,
                                 ))
    else:
        # Elaborate enrollment, redirect to the form
        return redirect('activities:enrollment_self', pk=obj.pk)

    return redirect(obj)


@require_POST
@require_lid
@transaction.atomic
def activity_unenrollment_self(request, pk):
    """
    Unenroll the person that is logged in for this activity.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    obj = get_object_or_404(Activity.objects.select_for_update(), pk=pk)

    if not check_unenrollment_allowed(request, obj):
        # If something went wrong, it will be stated in the django errors
        return redirect(obj)

    # No exception can occur here, this has been checked before
    participation = Participation.objects.select_for_update().get(person=request.person, event=obj)

    # If necessary, compensate the enrollment costs.
    from amelie.personal_tab import transactions
    transactions.remove_participation(participation)

    # Delete the participation
    participation.delete()

    messages.success(request,
                     _('You are now unenrolled for {activity}.').format(
                         activity=obj,
                     ))

    update_waiting_list(obj, request)

    # Redirect back to the activity
    return redirect(obj)


def activity_editenrollment(request, participation, obj):
    # If necessary, compensate the enrollment costs.
    from amelie.personal_tab import transactions
    transactions.remove_participation(participation)

    # Important to not delete the participation, as the spot on the waiting list will be given away.
    if participation.waiting_list:
        participation.enrollmentoptionanswer_set.all().delete()

        enrollmentoptions_forms = _build_enrollmentoptionsanswers_forms(obj, request.POST if request.POST else None,
                                                                        participation.person.user)

        # Make enrollmentoptions
        for form in enrollmentoptions_forms:
            if form.is_valid():
                answer = form.save(commit=False)
                answer.enrollment = participation
                answer.save()
                form.save_m2m()
    else:
        participation.delete()
        activity_enrollment_form(request, obj, person=None)


@require_lid
@transaction.atomic
def activity_editenrollment_self(request, pk):
    """
    Edit enrollment of the person that is logged in for this activity.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    obj = get_object_or_404(Activity.objects.select_for_update(), pk=pk)
    activity = obj

    # No exception can occur here, this has been checked before
    participation = Participation.objects.select_for_update().get(person=request.person, event=obj)

    if not check_unenrollment_allowed(request, obj, ignore_can_unenroll=participation.waiting_list):
        # If something went wrong, it will be stated in the django errors
        return redirect(obj)

    if request.method == 'POST':
        activity_editenrollment(request, participation, obj)
        # Redirect back to the activity
        return redirect(obj)
    else:
        enrollmentoptions_forms = _build_enrollmentoptionsanswers_forms(obj,
                                                                        request.POST if request.POST else None,
                                                                        request.user)
        update = True
        return render(request, "activity_enrollment_form.html", locals())


@require_board
@transaction.atomic
def activity_editenrollment_other(request, pk, person_id):
    """
    Edit enrollment of the person that is logged in for this activity.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    obj = get_object_or_404(Activity.objects.select_for_update(), pk=pk)
    person = get_object_or_404(Person, pk=person_id)
    activity = obj

    try:
        participation = Participation.objects.select_for_update().get(person=person, event=obj)
    except Participation.DoesNotExist:
        raise Http404

    if request.method == 'POST':
        activity_editenrollment(request, participation, obj)
        # Redirect back to the activity
        return redirect(obj)
    else:
        enrollmentoptions_forms = _build_enrollmentoptionsanswers_forms(obj,
                                                                        request.POST if request.POST else None,
                                                                        person.user)
        update = True
        return render(request, "activity_enrollment_form.html", locals())


@require_board
@transaction.atomic
def activity_unenrollment(request, pk, person_id):
    """
    Unenroll the given person for this activity.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    obj = get_object_or_404(Activity.objects.select_for_update(), pk=pk)

    participation = get_object_or_404(Participation.objects.select_for_update(), person_id=person_id, event=obj)
    person = participation.person

    if not check_unenrollment_allowed(request, obj, person, indirect=True, ignore_can_unenroll=True,
                                      ignore_unenrollment_period=True):
        # if something went wrong, it will be stated in the django errors
        return redirect(obj)

    if request.POST:
        if 'yes' in request.POST:
            # If necessary, compensate the enrollment costs.
            from amelie.personal_tab import transactions
            transactions.remove_participation(participation)

            # Delete the participation
            participation.delete()

            update_waiting_list(obj, request)

        messages.success(request,
                         _('{person} is now unenrolled for {activity}.').format(
                             person=participation.person,
                             activity=obj,
                         ))
        # Redirect back to the activity
        return redirect(obj)

    # Render the confirmation page
    return render(request, "activity_confirm_unenrollment.html", locals())


@require_actief
def activity_enrollment_person_search(request, pk):
    """
    Search for a person to enroll for this activity.
    """
    activity = get_object_or_404(Activity, pk=pk)
    if not activity.can_edit(request.person):
        raise PermissionDenied

    form = PersonSearchForm(request.POST if request.POST else None)
    if form.is_valid():
        return redirect('activities:enrollment_person', activity.id, form.cleaned_data['person'])

    # Render the template
    return render(request, "activity_enrollment_person_search.html", locals())


@require_lid
def activity_enrollment_self(request, pk):
    """
    Enroll yourself for an activity with an elaborate enrollment form.
    """
    activity = get_object_or_404(Activity, pk=pk)

    # Enrollment for an activity with enrollment options or a price may only be done through a special form.
    # However, since enrollment options possibly have costs associated with them, the person should have a mandate.
    # If the person has no mandate, then (s)he should be redirected to an explanation page.
    if not request.person.has_mandate_activities() and activity.has_costs():
        return render(request, "activity_enrollment_mandate.html", locals())

    return activity_enrollment_form(request, activity)


@require_lid
def activity_enrollment_person(request, pk, person_id):
    """
    Enroll someone else for an activity with an elaborate enrollment form.
    """
    activity = get_object_or_404(Activity, pk=pk)
    person = get_object_or_404(Person, id=person_id)

    return activity_enrollment_form(request, activity, person)


def _build_enrollmentoptionsanswers_forms(activity, data, user):
    forms = []

    for enrollmentoption in activity.enrollmentoption_set.all():
        prefix = 'enrollmentoption_{}'.format(enrollmentoption.pk)

        answer_type = ENROLLMENTOPTION_ANSWER_TYPES[enrollmentoption.content_type.model_class()]
        content_type = ContentType.objects.get_for_model(answer_type)
        instance = answer_type(enrollmentoption=enrollmentoption, content_type=content_type)

        form_type = ENROLLMENTOPTIONANSWER_FORM_TYPES[enrollmentoption.content_type.model_class()]

        # Make sure that if someone adjusts their enrollment and they have a spot with a limited capacity,
        # they still have the option to keep their spot.
        checked = False
        try:
            if form_type == EnrollmentoptionCheckboxAnswerForm:
                participation = Participation.objects.get(person__user=user, event=activity)
                unit = EnrollmentoptionCheckboxAnswer.objects.get(enrollmentoption=enrollmentoption,
                                                                  enrollment=participation)
                checked = unit.answer
            elif form_type == EnrollmentoptionNumericAnswerForm:
                participation = Participation.objects.get(person__user=user, event=activity)
                unit = EnrollmentoptionNumericAnswer.objects.get(enrollmentoption=enrollmentoption,
                                                                 enrollment=participation)
                checked = unit.answer > 0
        except (EnrollmentoptionCheckboxAnswer.DoesNotExist, EnrollmentoptionNumericAnswer.DoesNotExist,
                Participation.DoesNotExist):
            pass

        # If no data is given for this form, fill it from the database if possible
        initial = None
        try:
            participation = Participation.objects.get(person__user=user, event=activity)
            initial = {
                "answer": answer_type.objects.get(enrollmentoption=enrollmentoption, enrollment=participation).answer}
        except (Participation.DoesNotExist, answer_type.DoesNotExist):
            pass

        forms.append(
            form_type(enrollmentoption=enrollmentoption, checked=checked, data=data, prefix=prefix, instance=instance,
                      initial=initial))
    return forms


@require_lid
@transaction.atomic
def activity_enrollment_form(request, activity, person=None):
    """
    Elaborate enrollment form.

    This is used to enroll for activities with costs and/or enrollment options.
    or for enrolling other people.
    """

    # Lock the Activity object for updating, prevent concurrent (un)enrollments
    Activity.objects.select_for_update().get(pk=activity.pk)

    per_mandate = False
    indirect = person is not None
    activity_full = activity.enrollment_full()

    if person is None:
        person = request.person

    if not check_enrollment_allowed(request, activity, person=person, indirect=indirect,
                                    ignore_full=request.is_board, ignore_start_enrollment=indirect):
        # Django messages have been set in check_enrollment_allowed
        return redirect(activity)

    if indirect and not activity.can_edit(request.person):
        raise PermissionDenied

    per_mandate = (request.is_board or settings.PERSONAL_TAB_COMMITTEE_CAN_AUTHORIZE) \
                  and person.has_mandate_activities()

    enrollmentoptions_forms = _build_enrollmentoptionsanswers_forms(activity, request.POST if request.POST else None,
                                                                    person.user)
    if request.method == 'POST':

        if indirect:
            form_payment = PaymentForm(mandate=per_mandate, data=request.POST, files=request.FILES,
                                       waiting_list=activity_full, board=request.is_board)
            valid = all([form.is_valid() for form in enrollmentoptions_forms]) and form_payment.is_valid()
            errors = [form.errors for form in enrollmentoptions_forms]
        else:
            valid = all([form.is_valid() for form in enrollmentoptions_forms])
            errors = [form.errors for form in enrollmentoptions_forms]
            form_payment = None

        if valid:
            # Check if a participation is forced to skip waiting list
            force_skip_waiting_list = False
            if form_payment is not None and form_payment.cleaned_data.get('waiting_list', None) == "Skip":
                force_skip_waiting_list = True

            participation = Participation(person=person, event=activity, added_by=request.person,
                                          waiting_list=(activity_full and not force_skip_waiting_list))

            # Place a remark if someone else does the enrollment
            if indirect:
                participation.remark = 'Indirect enrollment.'
                participation.payment_method = form_payment.cleaned_data['method']
            else:
                participation.payment_method = Participation.PaymentMethodChoices.AUTHORIZATION

            # Make participation (Deelname)
            participation.save()

            # Make enrollmentoptions
            for form in enrollmentoptions_forms:
                answer = form.save(commit=False)
                answer.enrollment = participation
                answer.save()
                form.save_m2m()

            price, with_enrollmentoptions = participation.calculate_costs()

            if not price:
                # No payment method when nothing needs to be paid.
                participation.payment_method = Participation.PaymentMethodChoices.NONE
                participation.save()

            # Make transactions if there is a mandate
            if participation.payment_method == Participation.PaymentMethodChoices.AUTHORIZATION and (
                force_skip_waiting_list or not activity_full):
                from amelie.personal_tab import transactions
                transactions.add_participation(participation, request.person)

            # Send mail per preference. Always send email if indirect.
            if indirect or person.has_preference(name='mail_enrollment'):
                if activity_full:
                    activity_send_on_waiting_listmail(participation)
                else:
                    activity_send_enrollmentmail(participation)

            msg_waiting_list = ""
            if activity_full:
                msg_waiting_list = _("the waitinglist of")
            # Done
            if indirect:
                messages.success(request,
                                 _('{person} is now enrolled for {waiting_list} {activity}.').format(
                                     person=person,
                                     activity=activity,
                                     waiting_list=msg_waiting_list,
                                 ))
            else:
                messages.success(request,
                                 _('You are now enrolled for {waiting_list} {activity}.').format(
                                     activity=activity,
                                     waiting_list=msg_waiting_list
                                 ))
            return HttpResponseRedirect(activity.get_absolute_url())
        else:
            for error in errors:
                for key in error.keys():
                    messages.error(request, error[key][0])
    else:
        if indirect:
            form_payment = PaymentForm(mandate=per_mandate, waiting_list=activity_full, board=request.is_board)

    # Render the template
    return render(request, "activity_enrollment_form.html", locals())


@require_committee('MediaCie')
@never_cache
def photo_upload(request):
    folder = os.path.join(settings.MEDIA_ROOT, 'uploads/fotos')
    processing_folder = os.path.join(folder, '_processing')
    photos = []

    # Create processing dir if not exists
    if not os.path.isdir(processing_folder):
        if os.path.exists(processing_folder):
            os.remove(processing_folder)
        os.makedirs(processing_folder, exist_ok=True)

    for dir_path, dir_names, filenames in os.walk(folder):
        if "_processing" in dir_path:
            continue
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in ['.jpg', '.gif']):
                photos.append(os.path.relpath(os.path.join(dir_path, filename), folder))

    photos = list(sorted(
        photos, key=lambda filename: [(int(s) if s.isdecimal() else s.lower()) for s in re.split(r'(\d+)', filename)]
    ))

    choice_tuples = [(f, f) for f in photos]

    form = PhotoUploadForm(choice_tuples, initial={'photographer': request.person.pk, 'photos': photos})

    if request.method == 'POST':
        form = PhotoUploadForm(choice_tuples, request.POST)

        if form.is_valid():
            activity = form.cleaned_data["activity"]
            photographer = form.cleaned_data["photographer"]
            first_name = form.cleaned_data["first_name"]
            last_name_prefix = form.cleaned_data["last_name_prefix"]
            last_name = form.cleaned_data["last_name"]
            public = form.cleaned_data["public"]

            if photographer is not None:
                photographer = Photographer.objects.get_or_create(person=photographer)[0]
            else:
                photographer = Photographer.objects.get_or_create(first_name=first_name,
                                                                  last_name_prefix=last_name_prefix,
                                                                  last_name=last_name)[0]

            for photo in form.cleaned_data["photos"]:
                path = os.path.join(folder, photo)
                shutil.move(path, processing_folder)

            save_photos.delay(processing_folder, form.cleaned_data["photos"],
                              activity, photographer, public)
            messages.info(request, _("The photos are being uploaded. This might take while."))
            # Redirect to the result
            return HttpResponseRedirect(activity.get_photo_url())

    return render(request, "photo_upload.html", locals())


@require_committee('MediaCie')
@never_cache
def photo_upload_preview(request, filename):
    upload_folder = os.path.join(settings.MEDIA_ROOT, 'uploads/fotos')
    file_path = os.path.join(upload_folder, filename)

    # Make sure someone is not trying to path traverse and get a file outside the upload folder.
    file_path = os.path.realpath(file_path)
    common_prefix = os.path.commonprefix([file_path, upload_folder])
    if common_prefix != upload_folder:
        raise Http404(_("This picture does not exist."))

    # Make sure only JPG or GIF images can be previewed (only those extensions can be uploaded)
    file_extension = Path(file_path).suffix[1:].lower()
    if file_extension not in ["jpg", "jpeg", "gif"]:
        raise Http404(_("This picture does not exist."))

    # Make sure the file actually exists
    if not os.path.isfile(file_path):
        raise Http404(_("This picture does not exist."))

    # Create a small thumbnail for the file and return that as the response data
    image = Image.open(file_path)
    size_pixels = settings.THUMBNAIL_SIZES['small']
    # check whether the dimensions of the source are large enough such that a thumbnail is useful.
    if any(map(lambda b, d: b > d, image.size, size_pixels)):
        if file_extension in ['jpg', 'jpeg']:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.thumbnail(size_pixels, Image.ANTIALIAS)
            response = HttpResponse(content_type="image/jpeg")
            image.save(response, "JPEG")
            return response
        if file_extension == 'gif':
            image = image.convert('RGB')
            image.thumbnail(size_pixels, Image.ANTIALIAS)
            response = HttpResponse(content_type="image/jpeg")
            image.save(response, "JPEG")
            return response

    # In all other cases, just return the image directly.
    with open(file_path, "rb") as image_file:
        if file_extension in ['jpg', 'jpeg']:
            return HttpResponse(image_file.read(), content_type="image/jpeg")
        elif file_extension == "gif":
            return HttpResponse(image_file.read(), content_type="image/gif")
        else:
            raise Http404(_("This picture does not exist."))


class UploadPhotoFilesView(RequireCommitteeMixin, FormView):
    form_class = PhotoFileUploadForm
    success_url = reverse_lazy("activities:photo_upload")
    template_name = "photo_upload_files.html"
    abbreviation = "MediaCie"

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('photo_files')
        if form.is_valid():
            # Create upload folder if it does not exist
            upload_folder = os.path.join(settings.MEDIA_ROOT, 'uploads/fotos')
            os.makedirs(upload_folder, exist_ok=True)

            # Upload each file to the directory
            for f in files:
                # Move files to the photo upload directory
                with open(os.path.join(upload_folder, f.name), 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class ClearPhotoUploadDirView(RequireCommitteeMixin, View):
    abbreviation = "MediaCie"
    http_method_names = ['get', 'post']

    def get(self, request, *args, **kwargs):
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads/fotos')
        uploaded_files = [
            file for file in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, file))
        ]
        return render(request, "photo_upload_clear_confirm.html",
                      {"photos": uploaded_files})

    def post(self, request, *args, **kwargs):
        if 'yes' in request.POST:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads/fotos')
            for file in os.listdir(upload_dir):
                if os.path.isfile(os.path.join(upload_dir, file)):
                    os.remove(os.path.join(upload_dir, file))
        return redirect("activities:photo_upload")


def gallery_photo(request, pk, photo):
    activity = get_object_or_404(Activity, pk=pk)
    photo = get_object_or_404(activity.photos, id=photo)

    if not request.user.is_authenticated and (not activity.public or not photo.public):
        raise PermissionDenied

    photos = activity.photos.filter_public(request)
    previous = None
    first = None
    next = None
    last = None
    position = 0
    total = len(photos)

    for i, f in enumerate(photos):
        if f == photo:
            position = i + 1
            if i > 0:
                previous = photos[i - 1]
                first = photos[0]
            if i < total - 1:
                next = photos[i + 1]
                last = photos[total - 1]

    obj = activity
    return render(request, "gallery_photo.html", locals())


def gallery(request, pk, page=1):
    activity = get_object_or_404(Activity, pk=pk)
    if not activity.public and not request.user.is_authenticated:
        raise PermissionDenied

    # page = types.get_int(request.GET, 'pagina', default=1, min_value=1) #TODO
    limit = types.get_int(request.GET, 'limiet', default=24, min_value=1, max_value=999)
    photos = activity.photos.filter_public(request)
    pages = RangedPaginator(photos, limit)

    login_for_more = (len(photos) != len(activity.photos.all()))

    # Choose the correct page
    try:
        page = pages.page(page)
    except PageNotAnInteger:
        page = pages.page(1)
    except EmptyPage:
        page = pages.page(pages.num_pages)

    # Set the page range for the paginator
    pages.set_page_range(page, 7)

    # Done
    return render(request, "gallery.html", locals())


def photos(request, page=1):
    filters = Q(photos__gt=0)
    if "q" in request.GET:
        query = request.GET["q"]
        # No requirement of 3 characters or more because the request is not a
        # dynamic input field and will therefore stress the server less.
        filters &= Q(summary_nl__icontains=query) | Q(summary_en__icontains=query)

    activities = Activity.objects.filter_public(request).filter(filters).distinct().order_by('-end')

    only_public = not hasattr(request, 'user') or not request.user.is_authenticated
    if only_public:
        activities = activities.filter(photos__public=True)

    # page = types.get_int(request.GET, 'pagina', default=1, min_value=1) #TODO
    limit = types.get_int(request.GET, 'limit', default=12, min_value=1, max_value=999)
    pages = RangedPaginator(activities, limit)

    # Choose the correct page
    try:
        page = pages.page(page)
    except PageNotAnInteger:
        page = pages.page(1)
    except EmptyPage:
        page = pages.page(pages.num_pages)

    # Set the page range for the paginator
    pages.set_page_range(page, 7)

    # Done
    return render(request, "gallery_overview.html", locals())


def random_photo(request, after=None, type='landscape', format='small', response='json'):
    filters = Q()

    # Take the format into account
    if type == 'portrait':
        filters = filters & Q(**{'thumb_%s_height__gte' % format: F('thumb_%s_width' % format)})
    elif type == 'landscape':
        filters = filters & Q(**{'thumb_%s_width__gte' % format: F('thumb_%s_height' % format)})

    # Only photos after a specific period
    if after:
        filters = filters & Q(aangemaakt__gt=after)

    # Query
    try:
        photo = Attachment.objects.filter_public(request).filter(filters).order_by('?')[0]
    except:
        raise Http404(_('No photo'))

    # Done
    return photo.to_http_response(format=format, response=response)


@login_required
def activity_mailing(request, pk):
    obj = get_object_or_404(Activity, pk=pk)
    if not obj.can_edit(request.person):
        return redirect(obj)

    people = obj.participants.all()

    if not people.exists():
        raise Http404(_('No participants'))

    form = None
    page_class = 'activities'
    initial = {'email': obj.organizer.email, 'sender': obj.organizer.name}

    # Variables are used in the template, DO NOT REMOVE!
    longest_firstname = max([p.first_name for p in people if p.first_name is not None], key=len)
    longest_surname = max([p.last_name for p in people if p.last_name is not None], key=len)
    longest_address = max([p.address for p in people if p.address is not None], key=len)
    longest_postalcode = max([p.postal_code for p in people if p.postal_code is not None], key=len)
    longest_residence = max([p.city for p in people if p.city is not None], key=len)
    longest_country = max([p.country for p in people if p.country is not None], key=len)
    longest_student_number = '0123456'

    if request.method == "GET":
        form = MailingForm(initial=initial)
        preview_content = None
        preview_subject = None
    elif request.method == "POST":
        form = MailingForm(request.POST)
        if form.is_valid():
            if not form.cleaned_data['include_waiting_list']:
                people = obj.confirmed_participants
            if request.POST.get('preview', None):
                previews = form.build_multilang_preview(people[0])
            else:
                task = form.build_task(people)
                task.send()

                return redirect(obj)

    return render(request, 'includes/query/query_mailing.html', locals())


class ActivitySecurityMixin(object):
    """
    Mixin to check if the user is allowed to change an Activity.
    """

    def get_activity(self):
        """
        Get the related Activity object.

        Override of get_object() does not return the Activity object.
        """
        return self.get_object()

    def dispatch(self, request, *args, **kwargs):
        url = '%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, quote(request.get_full_path()))
        if not hasattr(request, 'person'):
            return HttpResponseRedirect(url)
        elif not self.get_activity().can_edit(request.person):
            return render(request, "403.html", {'reason': _('You do not have permissions to edit this activity')},
                          status=403)
        elif self.get_activity().cancelled:
            return render(request, "403.html", {'reason': _('You cannot edit this activity, because it is cancelled')},
                          status=403)
        else:
            return super(ActivitySecurityMixin, self).dispatch(request, *args, **kwargs)


class ActivityEditMixin(object):
    """
    Things that are shared by create and update, which are:
    1) The messages when no summary/description has been given
    2) The person who needs the form
    """

    def form_valid(self, form):
        response = super(ActivityEditMixin, self).form_valid(form)

        if self.request.POST.get("submit", False) == "save_and_options":
            response = HttpResponseRedirect(reverse('activities:enrollmentoption_list', args=[self.object.pk]))

        if not (form.instance.summary_en and form.instance.description_en):
            amelie_messages.with_actions(self.request, messages.WARNING,
                                         _('You did not fill in an English summary/description.'),
                                         [(_('edit event'),
                                           reverse('activities:edit',
                                                   args=[self.object.pk]))])

        if not (form.instance.summary_nl and form.instance.description_nl):
            amelie_messages.with_actions(self.request, messages.WARNING,
                                         _('You did not fill in a Dutch summary/description.'),
                                         [(_('edit event'),
                                           reverse('activities:edit',
                                                   args=[self.object.pk]))])

        return response

    def get_form_kwargs(self):
        kwargs = super(ActivityEditMixin, self).get_form_kwargs()

        kwargs["person"] = self.request.person if hasattr(self.request, "person") else None
        kwargs["current_organizer_pk"] = self.object.organizer.pk if hasattr(self.object, "organizer") else None

        return kwargs


class ActivityCreateView(RequireActiveMemberMixin, ActivityEditMixin, CreateView):
    model = Activity
    form_class = ActivityForm

    def get_context_data(self, **kwargs):
        context = super(ActivityCreateView, self).get_context_data(**kwargs)
        context["is_new"] = True

        return context


class ActivityUpdateView(ActivitySecurityMixin, ActivityEditMixin, UpdateView):
    model = Activity
    form_class = ActivityForm


class EnrollmentoptionListView(ActivitySecurityMixin, TemplateView):
    template_name = "activities/enrollmentoption_list.html"

    def get_activity(self):
        return Activity.objects.get(pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        activity_ins = self.get_activity()

        context = super(EnrollmentoptionListView, self).get_context_data(**kwargs)

        context['activity'] = activity_ins
        context['add_delete_allowed'] = not activity_ins.participants.exists()
        context['options_checkbox'] = EnrollmentoptionCheckbox.objects.filter(activity=activity_ins)
        context['options_food'] = EnrollmentoptionFood.objects.filter(activity=activity_ins)
        context['options_question'] = EnrollmentoptionQuestion.objects.filter(activity=activity_ins)
        context['options_numeric'] = EnrollmentoptionNumeric.objects.filter(activity=activity_ins)

        return context


class EnrollmentoptionCreateView(ActivitySecurityMixin, CreateView):
    template_name = 'activities/enrollmentoption_form.html'

    def get_activity(self):
        return Activity.objects.get(pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse('activities:enrollmentoption_list', args=[self.object.activity.pk])

    def get_context_data(self, **kwargs):
        context = super(EnrollmentoptionCreateView, self).get_context_data(**kwargs)

        context["option"] = self.model.__name__

        return context

    def get_form_class(self):
        if not self.model:
            raise ImproperlyConfigured("A EnrollmentoptionCreateView should have a model!")

        return ENROLLMENTOPTION_FORM_TYPES.get(self.model, None)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.activity = self.get_activity()
        self.object.content_type = ContentType.objects.get_for_model(self.model)

        return super(EnrollmentoptionCreateView, self).form_valid(form)

    def get(self, request, *args, **kwargs):
        activity_ins = self.get_activity()

        if activity_ins.participants.exists():
            messages.error(request,
                           _("This activity already has enrollments, therefore options can no longer be added!"))
            return HttpResponseRedirect(activity_ins.get_absolute_url())
        else:
            return super(EnrollmentoptionCreateView, self).get(self, request, args, kwargs)

    def post(self, request, *args, **kwargs):
        activity_ins = self.get_activity()

        if activity_ins.participants.exists():
            return HttpResponseForbidden(
                _("This activity already has enrollments, therefore options can no longer be added!"))
        else:
            return super(EnrollmentoptionCreateView, self).post(self, request, args, kwargs)


class EnrollmentoptionUpdateView(ActivitySecurityMixin, UpdateView):
    model = Enrollmentoption
    template_name = 'activities/enrollmentoption_form.html'

    def get_activity(self):
        return self.get_object().activity

    def get_form_class(self):
        """
        Looks at the type of this Enrollmentoption, and returns the corresponding form.
        """
        # The object of which we need to determine the type
        obj = self.get_object()

        # The dict is a mapping from type of the enrollment option to a formclass
        return ENROLLMENTOPTION_FORM_TYPES[obj.__class__]

    def get_object(self, queryset=None):
        # Return the leaf class of the Inschrijfoptie
        return super(EnrollmentoptionUpdateView, self).get_object(queryset).as_leaf_class()

    def get_success_url(self):
        return reverse('activities:enrollmentoption_list', args=(self.get_object().activity.pk,))


class EnrollmentoptionDeleteView(ActivitySecurityMixin, DeleteMessageMixin, DeleteView):
    model = Enrollmentoption
    template_name = "activities/enrollmentoption_confirm_delete.html"

    def get_activity(self):
        return self.get_object().activity

    def get(self, request, *args, **kwargs):
        if self.get_object().activity.participants.exists():
            messages.error(request, _("This activity already has enrollments, therefore options cannot be deleted!"))
            return HttpResponseRedirect(self.get_object().activity.get_absolute_url())
        else:
            return super(EnrollmentoptionDeleteView, self).get(request, *args, **kwargs)

    def get_delete_message(self):
        return _('Enrollment options %(object)s has been deleted' % {'object': self.get_object()})

    def get_success_url(self):
        return reverse('activities:enrollmentoption_list', args=(self.object.activity.pk,))

    def delete(self, request, *args, **kwargs):
        if self.get_object().activity.participants.exists():
            return HttpResponseForbidden(
                _("This activity already has enrollments, therefore options cannot be deleted!"))
        else:
            return super(EnrollmentoptionDeleteView, self).delete(request, *args, **kwargs)


class DataExport(PassesTestMixin, View):
    """
    View to execute a data export on a given query, and to a given format.
    This view will create a DataExportInformation object and store it before executing the export.
    """
    http_method_names = ["post"]

    needs_login = True
    reason = _('Only accessible for the board and the organisers of this activity.')

    def test_requirement(self, request):
        try:
            obj = Activity.objects.get(id=self.kwargs['pk'])
        except (Activity.DoesNotExist, KeyError):
            raise Http404(_("No activity found or invalid activity ID given."))

        is_board = hasattr(request, 'is_board') and request.is_board
        is_organization = obj.organizer in request.person.current_committees()

        return is_board or is_organization

    def post(self, request, pk=None):
        if pk is None:
            raise Http404(_("Invalid activity ID"))

        try:
            obj = Activity.objects.get(id=pk)
        except Activity.DoesNotExist:
            raise Http404(_("No activity found or invalid activity ID given."))

        form = ExportForm(request.POST)
        if form.is_valid():
            # Save the data export information and retrieve the export type to determine what to do.
            dei_id, export_type = form.save_data_export_information(request.user.person)

            if export_type == 'activity_export_csv':
                return DataExport.export_csv(request, obj.pk)
            elif export_type == 'activity_export_print':
                return DataExport.export_print(request, obj.pk)
            elif export_type == 'activity_export_deanonymise':
                return DataExport.export_html(request, obj.pk)
            else:
                # Redirect back to activity view with an error message.
                messages.warning(request, _(
                    "Could not create data export, because an unknown data-exporttype is provided."
                ))
                return HttpResponseRedirect(reverse('activities:activity', args=[obj.pk]))

        else:
            # Redirect back to activity view with an error message.
            messages.warning(request, _(
                "Could not create data export, because something went wrong while saving information about the export."
            ))
            return HttpResponseRedirect(reverse('activities:activity', args=[obj.pk]))

    @staticmethod
    def export_print(request, pk):
        """
        Returns an overview of participants for this activity that can be printed.
        """
        obj = get_object_or_404(Activity, pk=pk)
        if not obj.can_edit(request.person):
            raise PermissionDenied

        participation_set = obj.confirmed_participations.order_by('person__first_name')
        number_participants = obj.confirmed_participants.count() if obj.confirmed_participants else 0
        return render(request, "activity_enrollment_print.html", locals())

    @staticmethod
    def export_html(request, pk):
        """
        Returns a HTML overview of participants for this activity.
        """
        return activity(request, pk, deanonymise=True)

    @staticmethod
    def export_csv(request, pk):
        """
        Returns an overview of participants for this activity that can be printed.
        """
        obj = get_object_or_404(Activity, pk=pk)
        if not obj.can_edit(request.person):
            raise PermissionDenied

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=amelie-enrollments.csv'

        writer = csv.writer(response, dialect=csv.excel)
        writer.writerow(['Name', 'E-mail'] + [option.title for option in obj.enrollmentoption_set.all()])

        for participation in obj.confirmed_participations.order_by('person__first_name'):
            person = participation.person
            writer.writerow([mark_safe(str(person)), person.email_address] +
                            [answer.answer for answer in participation.enrollmentoptionanswer_set.all()])

        return response


class EventDeskMessageList(RequireActiveMemberMixin, ListView):
    model = EventDeskRegistrationMessage
    paginate_by = 50
    template_name = "activities/eventdesk/message_list.html"

    def get_context_data(self, **kwargs):
        context = super(EventDeskMessageList, self).get_context_data(**kwargs)
        now = timezone.now()
        one_week_ago = timezone.now() - datetime.timedelta(weeks=1)

        context['ia_event_email'] = settings.EVENT_DESK_NOTICES_DISPLAY_EMAIL

        current_activities = Activity.objects.filter(begin__gte=now).prefetch_related(
            'eventdeskregistrationmessage_set').order_by("begin")
        context['current_activities'] = [x for x in current_activities if x.can_edit(self.request.person)]
        past_activities = Activity.objects.filter(begin__gte=one_week_ago, end__lte=now).prefetch_related(
            'eventdeskregistrationmessage_set').order_by("-begin")
        context['past_activities'] = [x for x in past_activities if x.can_edit(self.request.person)]

        unmatched_messages = EventDeskRegistrationMessage.objects.filter(activity__isnull=True)[:15]
        context['unmatched_messages'] = unmatched_messages

        return context


class EventDeskHistory(RequireActiveMemberMixin, DetailView):
    model = Activity
    template_name = "activities/eventdesk/history.html"

    def render_to_response(self, *args, **kwargs):
        if not self.object.can_edit(self.request.person):
            raise PermissionDenied(_("You are not allowed to edit this activity"))
        return super(EventDeskHistory, self).render_to_response(*args, **kwargs)


class EventDeskMessageDetail(RequireActiveMemberMixin, DetailView):
    model = EventDeskRegistrationMessage
    template_name = "activities/eventdesk/detail.html"

    def render_to_response(self, *args, **kwargs):
        if self.object.activity and not self.object.activity.can_edit(self.request.person):
            raise PermissionDenied(_("You are not allowed to edit this activity"))
        if not self.object.activity and not self.request.is_board:
            raise PermissionDenied(_("You are not allowed to edit this activity"))
        return super(EventDeskMessageDetail, self).render_to_response(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(EventDeskMessageDetail, self).get_context_data(**kwargs)

        # Set up Google API connection to GMail
        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.EVENT_DESK_NOTICES_EMAIL,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )
        # Retrieve the message from Google
        msg_details = gmail_api.users().messages().get(id=self.object.message_id, userId='me',
                                                       format='metadata').execute()
        msg_raw = gmail_api.users().messages().get(id=self.object.message_id, userId='me', format='raw').execute()

        # Get the message from
        try:
            msg_from = [x for x in msg_details['payload']['headers'] if x['name'] == "From"][0]['value']
        except IndexError:
            msg_from = _("Unknown")

        # Get the message to
        try:
            msg_to = [x for x in msg_details['payload']['headers'] if x['name'] == "To"][0]['value']
        except IndexError:
            msg_to = _("Unknown")

        # Get the message subject
        try:
            msg_subject = [x for x in msg_details['payload']['headers'] if x['name'] == "Subject"][0]['value']
        except IndexError:
            msg_subject = _("Unknown")

        # Try to decode the message content
        msg_string = base64.urlsafe_b64decode(msg_raw['raw'].encode("UTF-8"))
        mime_msg = email.message_from_string(msg_string.decode("UTF-8"))
        content = None
        error_reason = _("Unknown error occurred.")
        for part in mime_msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    try:
                        content = part.get_payload(decode=True).decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            # UTF-8 not working, try Latin-1
                            content = part.get_payload(decode=True).decode("latin-1")
                        except UnicodeDecodeError:
                            # Latin-1 not working, try ASCII
                            content = part.get_payload(decode=True).decode("ASCII")
                    if content is not None:
                        break
                except UnicodeDecodeError:
                    error_reason = _("Message is not encoded in UTF-8, Latin-1 or ASCII, giving up...")
            elif content is None and part.get_content_type() == "text/html":
                import html2text
                try:
                    try:
                        text = part.get_payload(decode=True).decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            # UTF-8 not working, try Latin-1
                            text = part.get_payload(decode=True).decode("latin-1")
                        except UnicodeDecodeError:
                            # Latin-1 not working, try ASCII
                            text = part.get_payload(decode=True).decode("ASCII")
                    content = html2text.html2text(text, bodywidth=0)
                except UnicodeDecodeError:
                    error_reason = _("Message is not encoded in UTF-8, Latin-1 or ASCII, giving up...")

        context['message_details'] = msg_details
        context['message_from'] = msg_from
        context['message_to'] = msg_to
        context['message_subject'] = msg_subject
        context['message_text'] = content or _("Could not retrieve this message from Google. {}").format(error_reason)
        return context


class EventDeskMatch(RequireBoardMixin, FormView):
    form_class = EventDeskActivityMatchForm
    template_name = "activities/eventdesk/match.html"

    def __init__(self, *args, **kwargs):
        self.o = None
        super(EventDeskMatch, self).__init__(*args, **kwargs)

    def get_object(self):
        if self.o is None:
            self.o = EventDeskRegistrationMessage.objects.get(id=self.kwargs['pk'])
        return self.o

    def get_context_data(self, **kwargs):
        context = super(EventDeskMatch, self).get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context

    def get_form_kwargs(self):
        kwargs = super(EventDeskMatch, self).get_form_kwargs()
        msg = self.get_object()
        date_start = msg.get_event_start() - datetime.timedelta(weeks=1)
        date_end = msg.get_event_end() + datetime.timedelta(weeks=1)
        qs = Activity.objects.filter(begin__gt=date_start, end__lte=date_end).order_by('begin')
        kwargs.update({'activities': qs})
        return kwargs

    def get_success_url(self):
        return reverse("activities:eventdesk_detail", kwargs={"pk": self.get_object().pk})

    def form_valid(self, form):
        activity = form.cleaned_data['activity']
        message = self.get_object()
        message.activity = activity
        message.match_ratio = -1
        message.save()
        return HttpResponseRedirect(self.get_success_url())


class EventDeskRemoveMatch(RequireBoardMixin, DetailView):
    model = EventDeskRegistrationMessage

    def render_to_response(self, context, **response_kwargs):
        self.object.activity = None
        self.object.match_ratio = None
        self.object.save()
        return redirect("activities:eventdesk_detail", pk=self.object.pk)

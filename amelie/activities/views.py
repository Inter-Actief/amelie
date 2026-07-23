import shutil

import base64
import datetime
import email
import logging
import os
import re
import csv
from pathlib import Path
from typing import Dict, Union, Optional, Tuple

from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.forms import Form
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
from django.views.generic import ListView, DetailView
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

from amelie.activities.forms import ActivityForm, PhotoUploadForm, PhotoFileUploadForm, \
    ActivityEnrollmentOptionsForm, EnrollmentoptionAnswerForm, ENROLLMENTOPTION_FORM_TYPES, EventDeskActivityMatchForm
from amelie.activities.mail import activity_send_enrollmentmail, activity_send_on_waiting_listmail, \
    activity_send_price_change_mail, activity_send_enrollment_option_price_change_mail
from amelie.activities.models import Activity, DishPrice, Enrollmentoption, EnrollmentoptionCheckbox, \
    EnrollmentoptionFood, EnrollmentoptionQuestion, EventDeskRegistrationMessage, Restaurant, EnrollmentoptionNumeric
from amelie.activities.tasks import save_photos
from amelie.claudia.google import GoogleSuiteAPI
from amelie.files.models import Attachment
from amelie.calendar.models import Participation, Event
from amelie.members.forms import PersonSearchForm
from amelie.members.models import Person, Photographer
from amelie.members.query_forms import ActivityMailingForm
from amelie.personal_tab.models import ActivityTransaction
from amelie.tools import amelie_messages, types
from amelie.tools.const import TaskPriority
from amelie.tools.decorators import require_committee
from amelie.tools.forms import ExportForm, PeriodKeywordForm
from amelie.tools.calendar import ical_calendar
from amelie.tools.mixins import RequireActiveMemberMixin, DeleteMessageMixin, PassesTestMixin, RequireBoardMixin, \
    RequireCommitteeMixin, RequireMemberMixin
from amelie.tools.paginator import RangedPaginator

logger = logging.getLogger(__name__)


class ActivitiesICSView(View):
    """iCal-feed for activities."""
    def get(self):
        if self.kwargs.get('lang') is not None:
            translation.activate(self.kwargs.get('lang'))

        activities = Activity.objects.filter_public(self.request) \
            .filter(begin__gte=timezone.now() - datetime.timedelta(100)) \
            .order_by('begin')

        return HttpResponse(
            ical_calendar(_('Events of Inter-Actief'), activities, max_duration_before_split=datetime.timedelta(days=5)),
            content_type='text/calendar; charset=UTF-8'
        )


class ActivityICSView(View):
    """Returns the ical for an activity."""
    def get(self):
        activity: Activity = get_object_or_404(Activity, pk=self.kwargs.get('pk'))

        if not activity.public and not self.request.user.is_authenticated:
            raise PermissionDenied

        return HttpResponse(
            ical_calendar(_(activity.summary), [activity, ]),
            content_type='text/calendar; charset=UTF-8'
        )


class ActivityListView(ListView):
    """
    Gives an overview of all upcoming activities and recent past activities.
    """

    model = Event
    template_name = "activity_list.html"

    def get_queryset(self):
        qs = self.model.objects.filter_public(self.request)
        act_type = self.kwargs.get('act_type')
        if act_type is not None:
            qs = qs.filter(
                Q(activity__activity_label__name_en=act_type) | Q(activity__activity_label__name_nl=act_type)
            )
        return qs

    def get_context_data(self, *args, **kwargs):
        qs = self.get_queryset()
        return {
            'old_activities': [a.as_leaf_class() for a in qs.filter(end__lt=timezone.now()).order_by('-begin')[:10]],
            'new_activities': [a.as_leaf_class() for a in qs.filter(end__gte=timezone.now())],
            'only_open_enrollments': 'openEnrollments' in self.request.GET
        }

class OldActivityListView(ListView):
    """
    Gives an overview of past activities.
    You can filter on a date and on a few keywords.
    """

    model = Activity
    template_name = "activity_old.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form = None

    def _get_form(self):
        if self.form is None:
            self.form = PeriodKeywordForm(to_date_required=False, keywords_required=False, data=self.request.GET or None)
        return self.form

    def _get_params(self) -> Dict[str, Union[str, datetime.datetime]]:
        form = self._get_form()
        if form.is_valid():
            keywords = form.cleaned_data['keywords']
            start_date = form.cleaned_data['from_date']
            end_date = form.cleaned_data['to_date'] or timezone.now()
        else:
            keywords = ""
            start_date = form.fields['from_date'].initial
            end_date = form.fields['to_date'].initial

        # Convert dates to datetimes
        return {
            'keywords': keywords,
            'from_date': timezone.make_aware(datetime.datetime.combine(start_date, datetime.time())),
            'to_date': timezone.make_aware(datetime.datetime.combine(end_date, datetime.time()))
        }

    def get_queryset(self):
        qs = self.model.objects.filter_public(self.request).order_by('-end')
        get_params = self._get_params()

        # Filter date range
        qs = qs.filter(end__range=(get_params.get('from_date'), get_params.get('to_date')))

        # Filter keywords
        keywords = get_params.get('keywords')
        if keywords:
            qs = qs.filter(
                Q(summary_en__icontains=keywords) | Q(description_en__icontains=keywords) |
                Q(summary_nl__icontains=keywords) | Q(description_nl__icontains=keywords)
            )

        return qs

    def get_context_data(self, *args, **kwargs):
        return {
            'form': self._get_form(),
            'old_activities': self.get_queryset()
        }

class ActivityDetailView(DetailView):
    """Shows an activity."""
    model = Activity
    template_name = "activity.html"
    deanonymise = False

    def __init__(self, deanonymise=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deanonymise = deanonymise

    def get_context_data(self, **kwargs):
        if not self.object.public and not self.request.user.is_authenticated:
            raise PermissionDenied

        request_person: Optional[Person] = self.request.person if hasattr(self.request, 'person') else None

        context = super().get_context_data(**kwargs)
        context['obj'] = self.object  # Template laziness
        if self.object.participants:
            context['number_participants'] = self.object.participants.count()
            context['number_confirmed_participants'] = self.object.confirmed_participants.count()
            context['number_waiting_participants'] = self.object.waiting_participants.count()
        if self.request.user.is_authenticated and request_person:
            context['can_edit'] = self.object.can_edit(request_person)
        else:
            context['can_edit'] = False
        context['current_time'] = timezone.now()  # For determining whether to show the Cancel button.
        context['only_show_underage'] = hasattr(self.request, 'is_board') and self.request.is_board and (self.request.GET.get('underage') == "True")

        # Extra check to make sure that no sensitive data will be leaked
        if context['can_edit']:
            context['restaurants'] = Restaurant.objects.filter(
                enrollmentoptionfood__activity=self.object,
                dish__dishprice__enrollmentoptionfoodanswer__enrollmentoption__activity=self.object
            ).annotate(
                amount=Count('enrollmentoptionfood__activity'), total_price=Sum('dish__dishprice__price')
            ).distinct()
            # Add dishes to restaurant data
            for restaurant in context['restaurants']:
                restaurant.dishes = DishPrice.objects.filter(
                    enrollmentoptionfoodanswer__enrollmentoption__activity=self.object,
                    dish__restaurant=restaurant, enrollmentoptionfoodanswer__enrollment__waiting_list=False
                ).annotate(
                    amount=Count('enrollmentoptionfoodanswer', filter=Q(enrollmentoptionfoodanswer__enrollment__waiting_list=False)),
                    total_price=Sum('price', filter=Q(enrollmentoptionfoodanswer__enrollment__waiting_list=False))
                )

            context['total_price'] = sum(
                restaurant.dishes.aggregate(Sum('total_price')).get('total_price__sum', 0)
                for restaurant in context['restaurants']
            )
            context['total_amount'] = sum(
                restaurant.dishes.aggregate(Sum('amount')).get('amount__sum', 0)
                for restaurant in context['restaurants']
            )

        # Sorted set of participations that are used to show the enrollments
        context['participation_set'] = self.object.participation_set.order_by('added_on')

        context['confirmed_participation_set'] = self.object.participation_set.filter(waiting_list=False).order_by('added_on')
        context['public_participation_set'] = context['confirmed_participation_set'].filter(person__preferences__name="public_enrollment").order_by("person__first_name")
        context['anonymous_count'] = context['confirmed_participation_set'].count() - context['public_participation_set'].count()
        if context['only_show_underage']:
            context['confirmed_participation_set'] = [
                x for x in self.object.participation_set.filter(waiting_list=False).order_by('added_on')
                if x.person.age(at=self.object.begin) < 18
            ]
            context['confirmed_participation_set_turns_18_during_event'] = [
                x for x in context['confirmed_participation_set']
                if x.person.age(at=self.object.end) >= 18
            ]

        context['person_enrollment_public'] = request_person and request_person.has_preference(name="public_enrollment")
        context['waiting_participation_set'] = self.object.participation_set.filter(waiting_list=True).order_by('added_on')

        if request_person and context['waiting_participation_set'].filter(person=request_person).exists():
            # Spot is equal to the count of people that were earlier or at the same point in the waiting list than the person.
            added_on = context['waiting_participation_set'].get(person=request_person).added_on
            context['number_on_waiting_list'] = context['waiting_participation_set'].filter(added_on__lte=added_on).count()

        if request_person and self.object.participation_set.filter(person=request_person).exists():
            context['participation'] = self.object.participation_set.get(person=request_person)

        context['has_enrollment_options'] = self.object.has_enrollmentoptions

        # Data Export form for GDPR compliance.
        context['export_form'] = ExportForm()
        context['export_form'].fields['export_details'].initial = str(self.object)

        # Enable opengraph on this page
        context['metadata_enable_opengraph'] = True
        context['is_roomduty'] = request_person and request_person.is_room_duty()
        context['is_committee'] = request_person and self.object.organizer in request_person.current_committees().all()
        context['deanonymise'] = self.deanonymise

        return context


class ActivityDeleteView(RequireBoardMixin, DeleteView):
    """
    Deletes an activity.

    Activities may only be removed when these do not have any remaining enrollments left.

    Asks for a confirmation.
    """
    model = Activity
    template_name = "activity_confirm_delete.html"
    success_url = reverse_lazy('activities:activities')

    @transaction.atomic
    def form_valid(self, request, *args, **kwargs):
        """
        Make sure everyone is unenrolled from the activity, delete it, and then redirect to the success URL.
        """
        self.object: Activity = self.get_object()
        success_url = self.get_success_url()
        # Make sure everyone is unenrolled from the activity
        self.object.unenroll_all_participants(actor=self.request.person if hasattr(self.request, 'person') else None)
        self.object.delete()
        return HttpResponseRedirect(success_url)


class ActivityCancelView(RequireBoardMixin, DeleteView):
    """
    Cancels or re-publishes an activity (depending on the current status of this event).
    Note: Even though this view extends DeleteView, we override the Delete method so the Activity will not be deleted.

    Events may only be canceled if they have not yet started.
    Cancelling an activity is only allowed by the board due to possible transactions that should be undone.

    In the case of cancellation, this function removes all enrollments (and closes the option to enroll) and undoes the corresponding transactions.
    In the case of re-publishing, the cancellation will be removed, but enrollments will not be re-opened.

    Asks for a confirmation.
    """
    model = Activity
    template_name = "activity_confirm_cancellation.html"

    def get_success_url(self):
        return reverse('activities:activity', kwargs={'pk': self.object.pk})

    @transaction.atomic
    def form_valid(self, form):
        self.object: Activity = self.get_object()
        success_url = self.get_success_url()

        # If the event is already canceled, re-publish it.
        if self.object.cancelled:
            self.object.uncancel_activity()
            messages.success(
                self.request,
                _("{obj} has been successfully re-opened. Please note that any previous enrollments are not added "
                  "again and that enrollments will have to be manually re-opened.").format(obj=self.object)
            )
            return HttpResponseRedirect(success_url)

        # Else, cancel the activity.
        try:
            self.object.cancel_activity(actor=self.request.person if hasattr(self.request, 'person') else None)
            messages.success(self.request, _("{obj} was cancelled successfully.").format(obj=self.object))
            return HttpResponseRedirect(success_url)
        except ValueError:
            # Error during canceling. Only occurs if the activity has already started.
            messages.error(
                self.request, _("We were unable to cancel {obj}, since it has already started.").format(obj=self.object)
            )
            return redirect(self.object)


class ActivityEnrollSearchPersonView(RequireActiveMemberMixin, FormView):
    """
    Search for a person to enroll for this activity.
    """
    template_name = "activity_enrollment_person_search.html"
    form_class = PersonSearchForm

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activity = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['activity'] = self.activity
        return context

    def dispatch(self, request, *args, **kwargs):
        self.activity: Activity = get_object_or_404(Activity, pk=self.kwargs['pk'])
        if not (self.activity.can_edit(request.person) or request.person.is_room_duty()):
            raise PermissionDenied
        return super().dispatch(request=request, *args, **kwargs)

    def form_valid(self, form):
        return redirect('activities:enrollment_person', pk=self.activity.id, person_id=form.cleaned_data['person'])


class BaseActivityEnrollmentView(RequireMemberMixin, FormView):
    """
    Base view that has some shared functionality between Enrollment, Unenrollment and Edit views
    to handle if someone accesses the page for themselves or for someone else (indirect as board/roomduty).
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activity = None
        self.person = None
        self.indirect: bool = False

    def indirect_permisison_error_msg(self):
        return _("You are not allowed to access this activity page for other people.")

    def action_allowed_check(self) -> Tuple[bool, Optional[str]]:
        return False, _("Not implemented on base enrollment view.")

    def dispatch_post_hook(self) -> Optional[HttpResponse]:
        return None

    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        # Determine for which person the action is being taken
        self.activity: Activity = get_object_or_404(Activity, pk=self.kwargs['pk'])
        person_id = self.kwargs.get('person_id', None)
        if person_id:
            self.person: Person = get_object_or_404(Person, pk=person_id)
            self.indirect = True
        else:
            self.person: Person = request.person

        # Indirect action is only allowed by board members or roomduty members
        is_roomduty = request.person.is_room_duty()
        if self.indirect and not (self.activity.can_edit(request.person) or is_roomduty):
            messages.error(request, self.indirect_permisison_error_msg())
            return redirect(self.activity)

        # If action is not possible, set the reason in the django messages and return back to the activity view.
        action_allowed, reason = self.action_allowed_check()
        if not action_allowed:
            if reason is not None:
                messages.error(request, reason)
            return redirect(self.activity)

        resp = self.dispatch_post_hook()
        if resp is not None:
            return resp

        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def post(self, *args, **kwargs):
        # Locks the Activity object for updating, prevent concurrent (un)enrollments
        Activity.objects.select_for_update().get(pk=self.activity.pk)
        return super().post(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['activity'] = self.activity
        context['person'] = self.person
        context['indirect'] = self.indirect
        return context

class ActivityEnrollView(BaseActivityEnrollmentView):
    """
    Enrolls a person for an activity.

    If the activity is free and has no options, the enrollment is instant.
    If there are costs for the enrollment, or if it has any enrollment options, a form is shown.

    The person is either the currently logged-in person or,
    if the person is a board member and the `person_id` argument is given, it will enroll the selected person.
    """
    template_name = "activity_enrollment_form.html"
    form_class = ActivityEnrollmentOptionsForm

    def indirect_permisison_error_msg(self):
        return _("You are not allowed to enroll other people for this activity.")

    def action_allowed_check(self) -> Tuple[bool, Optional[str]]:
        return self.activity.check_enrollment_allowed(
            person=self.person, indirect=self.indirect, ignore_start_enrollment=self.indirect
        )

    def dispatch_post_hook(self) -> Optional[HttpResponse]:
        # If it's a self-enrollment for an activity with costs, and the person has no mandate, deny the enrollment.
        if not self.indirect and not self.person.has_mandate_activities() and self.activity.has_costs:
            return render(self.request, "activity_enrollment_mandate.html", {'activity': self.activity})
        return None

    def get_form_kwargs(self):
        return {
            'activity': self.activity,
            'participation': None,
            'add_indirect_form': self.indirect,
            'data': self.request.POST if self.request.method == 'POST' else None,
            'initial': {
                'indirect': {'waiting_list': self.activity.enrollment_full, 'board': self.request.is_board}
            } if self.indirect else {}
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['activity_full'] = self.activity.enrollment_full
        return context

    def send_enrollment_mail(self, participation: Participation):
        # Send mail if preference asks for it, or if it is an indirect enrollment
        if self.indirect or self.person.has_preference(name='mail_enrollment'):
            if participation.waiting_list:
                activity_send_on_waiting_listmail(participation)
            else:
                activity_send_enrollmentmail(participation)

    def set_enrolled_status_message(self, participation: Participation):
        # Set the status message in the request.
        if self.indirect:
            if participation.waiting_list:
                msg = _('{person} is now enrolled for the waitinglist of {activity}.')
            else:
                msg = _('{person} is now enrolled for {activity}.')
            messages.success(self.request, msg.format(person=self.person, activity=self.activity))
        else:
            if participation.waiting_list:
                msg = _('You are now enrolled for the waitinglist of {activity}.')
            else:
                msg = _('You are now enrolled for {activity}.')
            messages.success(self.request, msg.format(activity=self.activity))

    def get(self, *args, **kwargs):
        """
        Immediately enroll the person if it is their own enrollment, there are no options and the activity is free.
        Otherwise, render the enrollment form.
        """
        if not self.indirect and self.activity.enrollmentoption_set.count() == 0 and self.activity.price == 0:
            # Simple enrollment: no questions or costs. Enroll the person immediately
            enrollment_full = self.activity.enrollment_full
            participation = Participation(
                person=self.person,
                event=self.activity,
                added_by=self.request.person,
                waiting_list=enrollment_full
            )
            participation.save()

            # Maybe send a notification e-mail to the person and set a status message in the request.
            self.send_enrollment_mail(participation=participation)
            self.set_enrolled_status_message(participation=participation)

            # Redirect back to the activity details
            return redirect(self.activity)
        else:
            return super().get(*args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        # Check if the enrollment was indirect and the option to skip the waiting list for this enrollment was selected.
        force_skip_waiting_list = self.indirect and form.cleaned_data.get('indirect', {}).get('waiting_list', None) == "skip"

        # Enroll the person
        participation = Participation(
            person=self.person,
            event=self.activity,
            added_by=self.request.person,
            waiting_list=(self.activity.enrollment_full and not force_skip_waiting_list)
        )

        if self.indirect:
            participation.remark = 'Indirect enrollment.'

        participation.save()

        # Save enrollment option answers
        for subform_id, subform in form.forms.items():
            if isinstance(subform, EnrollmentoptionAnswerForm):
                answer = subform.save(commit=False)
                answer.enrollment = participation
                answer.save()
                subform.save_m2m()

        # Create personal tab transaction (if the activity is paid)
        price, with_enrollmentoptions = participation.calculate_costs()

        # Sanity check to disallow self-enrollment for options that cost money
        if price and not self.indirect and not self.person.has_mandate_activities():
            # Remember to delete the participation we created!
            participation.delete()
            return render(self.request, "activity_enrollment_mandate.html", {'activity': self.activity})

        if price and (force_skip_waiting_list or not self.activity.enrollment_full):
            from amelie.personal_tab import transactions
            transactions.add_participation(participation=participation, added_by=self.request.person)

        # Maybe send a notification e-mail to the person and set a status message in the request.
        self.send_enrollment_mail(participation=participation)
        self.set_enrolled_status_message(participation=participation)

        # Redirect back to the activity details
        return redirect(self.activity)


class ActivityUnenrollView(BaseActivityEnrollmentView):
    """
    Unenrolls a person for an activity.

    The person is either the currently logged-in person or,
    if the person is a board member and the `person_id` argument is given, it will unenroll the selected person.
    """
    template_name = "activity_confirm_unenrollment.html"
    form_class = Form

    def indirect_permisison_error_msg(self):
        return _("You are not allowed to unenroll other people for this activity.")

    def action_allowed_check(self) -> Tuple[bool, Optional[str]]:
        return self.activity.check_unenrollment_allowed(
            person=self.person, indirect=self.indirect,
            ignore_can_unenroll=self.indirect, ignore_unenrollment_period=self.indirect
        )

    @transaction.atomic
    def form_valid(self, form):
        # Retrieve the person's participation object and lock it for updating to prevent concurrent (un)enrollments
        participation = get_object_or_404(Participation, person=self.person, event=self.activity)
        Participation.objects.select_for_update().get(pk=participation.pk)

        # If necessary, compensate the person for the enrollment costs.
        from amelie.personal_tab import transactions
        transactions.remove_participation(participation)

        # Delete the participation
        participation.delete()

        # Set a status message for the user so they know the action is successful.
        if self.indirect:
            messages.success(self.request, _('{person} is now unenrolled for {activity}.').format(
                person=participation.person, activity=self.activity
            ))
        else:
            messages.success(self.request, _('You are now unenrolled for {activity}.').format(activity=self.activity))

        # Update the waitlist, and if the unenrollment was indirect, show if anyone new was promoted from the waitlist.
        new_participants = self.activity.update_waiting_list()
        if self.indirect:
            for np in new_participants:
                messages.info(
                    self.request, _('{person} has been promoted from the waiting list for {activity}.').format(
                        person=np.person.incomplete_name(), activity=self.activity
                    )
                )

        # Redirect back to the activity
        return redirect(self.activity)


class ActivityEditEnrollView(BaseActivityEnrollmentView):
    """
    Edits an enrollment of a person for an activity.

    The person is either the currently logged-in person or,
    if the person is a board member and the `person_id` argument is given, it will enroll the selected person.
    """
    template_name = "activity_enrollment_form.html"
    form_class = ActivityEnrollmentOptionsForm

    def indirect_permisison_error_msg(self):
        return _("You are not allowed to edit enrollments of other people for this activity.")

    def action_allowed_check(self) -> Tuple[bool, Optional[str]]:
        participation = Participation.objects.select_for_update().get(person=self.person, event=self.activity)
        return self.activity.check_unenrollment_allowed(
            person=self.person, ignore_can_unenroll=participation.waiting_list
        )

    def get_form_kwargs(self):
        # Retrieve the person's participation object and lock it for updating to prevent concurrent (un)enrollments
        participation = get_object_or_404(Participation, person=self.person, event=self.activity)
        Participation.objects.select_for_update().get(pk=participation.pk)
        return {
            'activity': self.activity,
            'participation': participation,
            'add_indirect_form': False,  # Edits can't modify the waiting list placement.
            'data': self.request.POST if self.request.method == 'POST' else None,
            'initial': {
                'indirect': {'waiting_list': self.activity.enrollment_full, 'board': self.request.is_board}
            } if self.indirect else {}
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['update'] = True
        return context

    def send_enrollment_mail(self, participation: Participation):
        # Send mail if preference asks for it, or if it is an indirect enrollment
        if self.indirect or self.person.has_preference(name='mail_enrollment'):
            if participation.waiting_list:
                activity_send_on_waiting_listmail(participation)
            else:
                activity_send_enrollmentmail(participation)

    def set_enrolled_status_message(self, participation: Participation):
        # Set the status message in the request.
        if self.indirect:
            if participation.waiting_list:
                msg = _('{person} is now enrolled for the waitinglist of {activity}.')
            else:
                msg = _('{person} is now enrolled for {activity}.')
            messages.success(self.request, msg.format(person=self.person, activity=self.activity))
        else:
            if participation.waiting_list:
                msg = _('You are now enrolled for the waitinglist of {activity}.')
            else:
                msg = _('You are now enrolled for {activity}.')
            messages.success(self.request, msg.format(activity=self.activity))

    @transaction.atomic
    def form_valid(self, form):
        from amelie.personal_tab import transactions
        # It is important to NOT delete the Participation, because the person's spot in the activity
        # or on the waiting list could be given away to the next waiting list entry.
        # So we need to update the enrollment options of the participation in-place

        participation: Optional[Participation] = form.participation
        if participation is None:
            raise ValueError(_("Participation not found while editing enrollment."))

        if not participation.waiting_list:
            # If this is a regular Participation (not waiting list), we need to remove the old transaction from
            # their personal tab to not charge them twice and to be able to re-add the updated costs later
            transactions.remove_participation(participation, added_by=self.request.person, is_edited_participation=True)

        # Save enrollment option answers
        for subform_id, subform in form.forms.items():
            if isinstance(subform, EnrollmentoptionAnswerForm):
                answer = subform.save(commit=False)
                answer.enrollment = participation
                answer.save()
                subform.save_m2m()

        if not participation.waiting_list:
            # If this is a regular Participation (not waiting list), we need to re-add
            # the transaction to update the costs on the personal tab
            transactions.add_participation(participation, added_by=self.request.person, is_edited_participation=True)

        # Redirect back to the activity details
        return redirect(self.activity)


def activity_random_photo(request, pk, *args, **kwargs):
    """ Returns a random photo of a specific activity. """
    act = get_object_or_404(Activity, pk=pk)
    photo = act.random_photo(only_public=not hasattr(request, 'person'))

    # Generate a JSON response
    if photo:
        return photo.to_http_response(format='medium', response='json')

    # No photo
    raise Http404(_('No photo'))


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
            if any(filename.lower().endswith(ext) for ext in PhotoFileUploadForm.allowed_extensions):
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

            # During field validation, it is checked whether one of those is present
            if first_name and last_name:
                photographer = Photographer.objects.get_or_create(first_name=first_name,
                                                                  last_name_prefix=last_name_prefix,
                                                                  last_name=last_name)[0]
            else:
                photographer = Photographer.objects.get_or_create(person=photographer)[0]


            for photo in form.cleaned_data["photos"]:
                path = os.path.join(folder, photo)
                shutil.move(path, processing_folder)

            save_args = [processing_folder, form.cleaned_data["photos"], activity, photographer, public]
            save_photos.s(*save_args).set(priority=TaskPriority.HIGH).delay()
            messages.info(request, _("The photos are now being processed in the background."
                                     "Photos will show up on the activity as they are processed, "
                                     "you can refresh the page to follow the progres."))
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
    if file_extension not in PhotoFileUploadForm.allowed_extensions:
        raise Http404(_("This picture does not exist."))

    # Make sure the file actually exists
    if not os.path.isfile(file_path):
        raise Http404(_("This picture does not exist."))

    # Create a small thumbnail for the file and return that as the response data
    image = Image.open(file_path)
    size_pixels = settings.THUMBNAIL_SIZES['small']

    # check whether the dimensions of the source are large enough such that a thumbnail is useful.
    if any(map(lambda b, d: b > d, image.size, size_pixels)):
        if image.mode != 'RGB' or file_extension == 'gif':
            image = image.convert('RGB')
        image.thumbnail(size_pixels, Image.LANCZOS)
        response = HttpResponse(content_type="image/jpeg")
        image.save(response, "JPEG")
        return response

    # In all other cases, just return the image directly.
    with open(file_path, "rb") as image_file:
        # Can safely return since file extension was checked earlier on
        if file_extension == "jpg":
            file_extension = "jpeg" # image/jpg does not exist
        return HttpResponse(image_file.read(), content_type=f'image/{file_extension}')


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
    photo_id = photo
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
    with_permissions = hasattr(request, "is_board") and request.is_board or hasattr(request, "person") and request.person.is_in_committee("MediaCie")
    nextVisibility = f'Change to {"Private" if photo.public else "Public"}'

    return render(request, "gallery_photo.html", locals())

@require_committee('MediaCie')
def delete_photo(request, pk, photo):
    activity = get_object_or_404(Activity, pk=pk)
    photo: Attachment = get_object_or_404(activity.photos, id=photo)

    if not request.user.is_authenticated and (not activity.public or not photo.public):
        raise PermissionDenied

    photo.delete()

    return redirect(activity)

@require_committee('MediaCie')
def toggle_visibility(request, pk, photo):
    activity = get_object_or_404(Activity, pk=pk)
    photo_id = photo
    photo: Attachment = get_object_or_404(activity.photos, id=photo_id)

    if not request.user.is_authenticated and (not activity.public or not photo.public):
        raise PermissionDenied

    photo.public = not photo.public
    photo.save(create_thumbnails=False)

    return redirect("activities:gallery_photo", pk=pk, photo=photo_id)

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
        form = ActivityMailingForm(initial=initial)
        preview_content = None
        preview_subject = None
    elif request.method == "POST":
        form = ActivityMailingForm(request.POST)
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

    def form_valid(self, form):
        # If the date or price has changed, we have to update any existing transactions to the new activity date/price.
        # The existing transactions are refunded and will be re-created on the same date.
        person = self.request.person
        if person is None:
            raise Exception("Updating requires a person")

        old_obj = self.get_object()
        new_obj = form.instance

        # Save changes to the parent activity so new transactions are calculated correctly in case of a new price/date
        response = super().form_valid(form)

        # Determine if any activity fields that have an impact on the participation transactions have been changed
        needs_new_transactions = False
        change_reasons = []
        # If the activity start date is moved to a different day, the transactions need to be moved to the new date.
        if form.cleaned_data['begin'].date() != old_obj.begin.date():
            needs_new_transactions = True
            change_reasons.append(_("start date was changed"))

        # If the activity price is changed, the transactions need to be recreated with the new price
        if form.cleaned_data['price'] != old_obj.price:
            needs_new_transactions = True
            change_reasons.append(_("price was changed"))
            activity_send_price_change_mail(old_obj, new_obj)

        if old_obj is not None and needs_new_transactions:
            # Undo and create new transactions
            from amelie.personal_tab import transactions
            # Only consider participations paid by a mandate
            # (to avoid creating transactions for members without a personal tab mandate)
            for participation in old_obj.participation_set.filter(payment_method=Participation.PaymentMethodChoices.AUTHORIZATION):
                # Note - reason text is max 200 chars!
                reason = _("Activity '{activity}' was changed (reversal of old transaction) ({change_reasons})").format(
                    activity=str(old_obj)[:90], change_reasons=", ".join(change_reasons)
                )
                transactions.participation_transaction(
                    participation,
                    reason=reason,
                    cancel=True, added_by=person
                )

                # Create a new transaction
                price, with_enrollment_options = participation.calculate_costs()
                # Note - reason text is max 200 chars!
                reason = _("Activity '{activity}' was changed (addition of new transaction) ({change_reasons})").format(
                    activity=str(new_obj.summary)[:90], change_reasons=", ".join(change_reasons)
                )

                # Can't use transactions.participation_transaction because we need to override the date.
                transaction = ActivityTransaction(price=price, description=reason,
                                                  participation=participation, event=old_obj,
                                                  person=participation.person, date=new_obj.begin,
                                                  with_enrollment_options=with_enrollment_options, added_by=person)
                transaction.save()

        return response


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

    def form_valid(self, form):
        # If the price has changed, we have to update any existing transactions to the new activity price.
        # The existing transactions are refunded and will be re-created on the same date.
        person = self.request.person
        if person is None:
            raise Exception("Updating requires a person")

        old_obj = self.get_object()
        new_obj = form.instance

        # Save changes to the parent activity so new transactions are calculated correctly in case of a new price/date
        response = super().form_valid(form)

         # Determine if any activity fields that have an impact on the participation transactions have been changed
        needs_new_transactions = False
        change_reasons = []

        # If the enrollment option price is changed, the transactions need to be recreated with the new price
        if "price_extra" in form.cleaned_data and form.cleaned_data["price_extra"] != old_obj.price_extra:
            needs_new_transactions = True
            change_reasons.append(_("enrollment option price was changed"))
            activity_send_enrollment_option_price_change_mail(old_obj, new_obj)

        if old_obj is not None and needs_new_transactions:
            # Undo and create new transactions
            from amelie.personal_tab import transactions
            # Only consider participations paid by a mandate
            # (to avoid creating transactions for members without a personal tab mandate)
            for participation in old_obj.activity.participation_set.filter(payment_method=Participation.PaymentMethodChoices.AUTHORIZATION):
                # Note - reason text is max 200 chars!
                reason = _("An enrollment option for activity '{activity}' was changed (reversal of old transaction) ({change_reasons})").format(
                    activity=str(old_obj.activity)[:80], change_reasons=", ".join(change_reasons)
                )
                transactions.participation_transaction(
                    participation,
                    reason=reason,
                    cancel=True, added_by=person
                )

                # Create a new transaction
                price, with_enrollment_options = participation.calculate_costs()
                # Note - reason text is max 200 chars!
                reason = _("An enrollment option for activity '{activity}' was changed (addition of new transaction) ({change_reasons})").format(
                    activity=str(new_obj.activity.summary)[:80], change_reasons=", ".join(change_reasons)
                )

                # Can't use transactions.participation_transaction because we need to override the date.
                transaction = ActivityTransaction(price=price, description=reason,
                                                  participation=participation, event=old_obj.activity,
                                                  person=participation.person, date=new_obj.activity.begin,
                                                  with_enrollment_options=with_enrollment_options, added_by=person)
                transaction.save()

        return response

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
        is_organization = hasattr(request, 'person') and obj.organizer in request.person.current_committees()
        is_roomduty = hasattr(request, 'person') and request.person.is_room_duty()

        return is_board or is_organization or is_roomduty

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
        Returns an HTML overview of participants for this activity. (Regular ActivityView but deanonimised).
        """
        av = ActivityDetailView(deanonymise=True)
        av.setup(request=request, pk=pk)
        return av.get(request=request, pk=pk)

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
        past_activities = Activity.objects.filter(begin__gte=one_week_ago, begin__lte=now).prefetch_related(
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

from typing import Optional, Dict

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.generic import DetailView, FormView

from amelie.activities.forms import ActivityManualPaymentForm
from amelie.activities.views import ActivityDetailView
from amelie.calendar.models import Participation
from amelie.members.models import Person
from amelie.personal_tab.models import ManualPaymentSettlement
from amelie.tools.mixins import RequireAjaxMixin, RequireCommitteeMixin


class ActivityParticipationsView(RequireAjaxMixin, ActivityDetailView):
    template_name = "includes/activity_participants_table.html"


class ActivityParticipationPaymentsView(RequireAjaxMixin, RequireCommitteeMixin, DetailView):
    template_name = "includes/activity_participation_payments.html"
    model = Participation
    abbreviation = settings.ROOM_DUTY_ABBREVIATION

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_person: Optional[Person] = self.request.person if hasattr(self.request, 'person') else None
        context['transactions'] = self.object.activitytransaction_set.all()
        context['is_roomduty'] = request_person and request_person.is_room_duty()
        context['is_committee'] = request_person and self.object.event.organizer in request_person.current_committees().all()
        context['status_msg'] = self.request.GET.get('msg')
        return context

class ActivityParticipationCreatePaymentView(RequireAjaxMixin, RequireCommitteeMixin, FormView):
    template_name = "includes/activity_participation_create_payment.html"
    abbreviation = settings.ROOM_DUTY_ABBREVIATION
    form_class = ActivityManualPaymentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_person: Optional[Person] = self.request.person if hasattr(self.request, 'person') else None
        context['object'] = Participation.objects.get(pk=self.kwargs['pk'])
        context['transactions'] = [t for t in context['object'].activitytransaction_set.all() if not t.is_paid()]
        context['transactions_total'] = sum(t.price for t in context['transactions'])
        context['is_roomduty'] = request_person and request_person.is_room_duty()
        context['is_committee'] = request_person and context['object'].event.organizer in request_person.current_committees().all()
        return context

    def get_success_url(self, query: Optional[Dict] = None):
        return reverse('activities:activity_participation_payments', kwargs={
            'activity_id': self.kwargs['activity_id'], 'pk': self.kwargs['pk']
        }, query=query)

    def form_valid(self, form):
        # Get the transactions that need to be paid.
        participation = Participation.objects.get(pk=self.kwargs['pk'])
        payment_method = form.cleaned_data['payment_method']
        settlement = participation.mark_as_paid(payment_method=payment_method, actor=self.request.person)
        if settlement:
            return HttpResponseRedirect(self.get_success_url(query={'msg': 'created'}))
        else:
            return HttpResponseRedirect(self.get_success_url(query={'msg': 'no_transactions'}))

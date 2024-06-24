from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _l
from django.views.generic import TemplateView

from amelie.calendar.models import Participation
from amelie.tools.mixins import RequireBoardMixin


class PayParticipationView(RequireBoardMixin, TemplateView):
    template_name = "confirm_payment.html"

    def get_context_data(self, **kwargs):
        context = super(PayParticipationView, self).get_context_data()
        participation = get_object_or_404(Participation, pk=self.kwargs['pk'])
        context['obj'] = participation
        return context

    def post(self, request, *args, **kwargs):
        participation = get_object_or_404(Participation, pk=self.kwargs['pk'])
        if 'yes' in request.POST:
            participation.cash_payment_made = True
            remark = _l(
                f"Payment registered on {timezone.now().strftime('%d-%m-%Y')} by {request.user.person.incomplete_name()}")
            participation.remark += f" {remark}"
            participation.save()
            messages.success(request, _l("Cash payment registered!"))
        return redirect('activities:activity', participation.event_id)



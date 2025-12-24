import json
import logging
import traceback

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import FormView, ListView, DeleteView
from pyipp import IPPConnectionError

from amelie.personal_tab.forms import PrintDocumentForm
from amelie.personal_tab.models import PrintLogEntry, Article, CustomTransaction
from amelie.tools.decorators import require_superuser
from amelie.tools.mixins import RequirePersonalTabAuthorizationOrActiveMemberMixin, RequireBoardMixin


@require_superuser
def printer_status(request, printer_key):
    available_printers = settings.PERSONAL_TAB_PRINTERS.keys()
    if printer_key not in available_printers:
        raise Http404("Printer not found.")

    try:
        from amelie.tools.ipp_printer import IPPPrinter
        printer = IPPPrinter(printer_key=printer_key)
        attributes = printer.printer_attributes()
        jobs = printer.printer_jobs()
        return HttpResponse(json.dumps({
            'attributes': attributes,
            'jobs': jobs
        }, indent=2, default=lambda o: str(repr(o))), content_type='application/json')
    except IPPConnectionError as e:
        return HttpResponse(json.dumps({
            'error_code': 500,
            'error_class': e.__class__.__name__,
            'error_message': str(e),
        }, indent=2, default=lambda o: str(repr(o))), content_type='application/json', status=500)


class PrintIndexView(RequirePersonalTabAuthorizationOrActiveMemberMixin, FormView):
    """
    View to print documents on the Inter-Actief printer.

    Only available to members with personal tab authorization, or active members.
    """
    form_class = PrintDocumentForm
    success_url = reverse_lazy('personal_tab:print_index')
    template_name = 'print_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['person'] = self.request.user.person
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['max_file_size'] = f"{settings.PERSONAL_TAB_PRINTER_MAX_FILE_SIZE / 1024 / 1024:.2f} MB"
        context['max_file_size_bytes_int'] = settings.PERSONAL_TAB_PRINTER_MAX_FILE_SIZE
        page_price = Article.objects.get(id=settings.PERSONAL_TAB_PRINTER_PAGE_ARTICLE_ID).price
        context['per_page_cost'] = f"{page_price:.2f}"
        if self.request.user.is_superuser:
            context['available_printers'] = [(k, p['name']) for k, p in settings.PERSONAL_TAB_PRINTERS.items()]
        return context

    def form_valid(self, form):
        try:
            print_log: PrintLogEntry = form.save(request=self.request)
            messages.success(self.request, _("Document '{name}' with {pages} page(s) was queued for printing successfully.").format(
                name=print_log.document_name, pages=print_log.page_count
            ))
        except Exception as e:
            trace = traceback.format_exc()
            logging.error(f"Error while printing: {str(e.__class__.__name__)} - {trace}")
            messages.error(self.request, _("Error while submitting print to the printer. No prints were registered. Error: {ex}").format(ex=str(e.__class__.__name__)))
        return super().form_valid(form=form)


class PrintRefundConfirmView(RequireBoardMixin, DeleteView):
    model = PrintLogEntry
    template_name = 'print_refund.html'
    success_url = reverse_lazy('personal_tab:print_log')

    def get_object(self, *args, **kwargs):
        obj = super().get_object(*args, **kwargs)
        if not obj.transaction:
            raise Http404("Cannot refund a print that does not have a transaction.")
        return obj

    def _refund_transaction(self):
        old_transaction = self.object.transaction
        CustomTransaction.objects.create(
            person=old_transaction.person,
            added_by=self.request.user.person,
            description=_("Refund for print, transaction #{tid}").format(tid=old_transaction.id),
            price=-old_transaction.price,
        )
        self.object.transaction = None
        self.object.save()
        messages.success(self.request, _("Print by {person} was refunded successfully.").format(person=self.object.actor))

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        self._refund_transaction()
        return super().delete(request=request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        self._refund_transaction()
        return super().form_valid(form=form)


class PrintLogView(RequireBoardMixin, ListView):
    model = PrintLogEntry
    template_name = 'print_log_list.html'
    paginate_by = 30
    ordering = ['-timestamp']  # Most recent first
    context_object_name = 'print_logs'

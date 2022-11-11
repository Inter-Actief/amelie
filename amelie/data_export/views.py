import os
import uuid
from django.db import transaction
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView
from django.utils.translation import gettext as _

from amelie.data_export.forms import DataExportCreateForm
from amelie.data_export.models import DataExport, ApplicationStatus
from amelie.data_export.tasks import export_data
from amelie.data_export.templatetags.status_icon import status_icon
from amelie.tools.http import HttpJSONResponse


class RequestDataExportView(FormView):
    model = DataExport
    form_class = DataExportCreateForm
    template_name = "data_export/dataexport_form.html"

    data_export = None

    def get_success_url(self):
        if self.data_export:
            return self.data_export.get_absolute_url()
        else:
            return reverse("data_export:request_export")

    def get_context_data(self, **kwargs):
        context = super(RequestDataExportView, self).get_context_data(**kwargs)
        context['already_has_export'] = False

        # Check if this person already has a DataExport which is not expired.
        # If they have one, delete the export if it is expired, otherwise set a flag in the context to display an error.
        if self.request.user.is_authenticated:
            try:
                data_export = DataExport.objects.get(person=self.request.person)

                if data_export.is_expired:
                    data_export.delete()
                else:
                    context['already_has_export'] = True

            except DataExport.DoesNotExist:
                pass

        return context

    def form_valid(self, form):
        # Generate a download code
        download_code = str(uuid.uuid4())

        with transaction.atomic():
            # Create a DataExport object
            self.data_export = DataExport.objects.create(
                download_code=download_code,
                person=self.request.person,
            )

            # Add ApplicationStatuses for the checked applications
            for application_str in form.cleaned_data.get("applications", []):
                ApplicationStatus.objects.create(
                    data_export=self.data_export,
                    application=application_str,
                    status=ApplicationStatus.StatusChoices.NOT_STARTED
                )

        # Start generating the export
        e = export_data.delay(self.data_export)

        # Redirect to the success page (DownloadView)
        return HttpResponseRedirect(self.get_success_url())


class DataExportDetailView(DetailView):
    model = DataExport

    def get_context_data(self, **kwargs):
        context = super(DataExportDetailView, self).get_context_data(**kwargs)

        if context['object'].filename and os.path.isfile(context['object'].filename):
            context['object_size'] = os.path.getsize(context['object'].filename)
        else:
            context['object_size'] = 0

        return context

    def get_slug_field(self):
        return 'download_code'


class DataExportAjaxView(View):
    def get(self, request, slug):
        try:
            data_export = DataExport.objects.get(download_code=slug)
        except DataExport.DoesNotExist:
            raise Http404(_("Could not find a data export download with this code."))

        if data_export.filename and os.path.isfile(data_export.filename):
            object_size = os.path.getsize(data_export.filename)
        else:
            object_size = 0

        details_html = render_to_string('data_export/dataexport_download_details.html', context={
            'object': data_export,
            'object_size': object_size
        })

        return HttpJSONResponse({
            'applications': [{
                'name': str(application.application),
                'status': str(application.status),
                'status_html': status_icon(application)
            } for application in data_export.exported_applications.all()],
            'done': data_export.is_ready,
            'details_html': details_html
        })


class DataExportDownloadView(View):
    def get(self, request, slug):
        try:
            data_export = DataExport.objects.get(download_code=slug)
        except DataExport.DoesNotExist:
            raise Http404(_("Could not find a data export download with this code."))

        if not data_export.filename or not os.path.exists(data_export.filename):
            raise Http404(_("Could not find a data export download with this code."))

        with open(data_export.filename, 'rb') as export_file:
            response = HttpResponse(export_file.read(), content_type="application/zip")
            response['Content-Disposition'] = 'inline; filename=data_export_{}_{}.zip'.format(
                data_export.person.slug, str(data_export.complete_timestamp).replace(" ", "-")
            )

        data_export.download_count += 1
        data_export.save()
        return response

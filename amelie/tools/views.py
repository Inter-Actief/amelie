import json
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.template.loader import get_template
from django.utils import translation
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView
from django.views.generic.base import TemplateView

from amelie.iamailer.mailer import render_mail
from amelie.members.models import Person, Membership, UnverifiedEnrollment
from amelie.personal_tab.models import Authorization
from amelie.tools.decorators import require_superuser
from amelie.tools.documenso import AMELIE_REFERENCE_REGEX
from amelie.tools.forms import MailTemplateTestForm, ExportTypeSelectForm
from amelie.tools.http import HttpJSONResponse
from amelie.tools.mail import person_dict
from amelie.tools.mixins import RequireSuperuserMixin, RequireBoardMixin, RequireAllowlistedIPMixin
from amelie.tools.models import DataExportInformation


@require_superuser
def logging_config(request):
    """
    Display the current logging configuration.
    """

    rootlogger = logging.getLogger()

    manager = rootlogger.manager

    d = manager.loggerDict

    keys = list(d.keys())
    keys.sort()

    loggers = {}

    for k in keys:
        logger = d[k]
        if not isinstance(logger, logging.PlaceHolder):
            loggers[k] = logger

    handlers = set([handler for logger in loggers.values() for handler in logger.handlers])

    keys = list(loggers.keys())
    keys.sort()

    logger_list = []

    for k in keys:
        logger = loggers[k]
        logger_list.append(logger)

    return render(request, 'tools_logging_config.html', locals())


@require_superuser
def flash(request):
    """
    Display some flash messages for debugging purposes.
    """

    messages.debug(request, 'Some SQL statements were executed.')
    messages.info(request, 'Three credits remain in your account.')
    messages.success(request, 'Profile details updated.')
    messages.warning(request, 'Your account expires in three days.')
    messages.error(request, 'Document deleted.')

    return render(request, 'tools_logging_config.html')


class MailPreview(RequireSuperuserMixin, TemplateView):
    template_name = "weekmail/weekmail_preview.html"

    def render_to_response(self, context, **response_kwargs):
        template = get_template(context.get("template_name", "iamailer/testmail.mail"))

        old_language = translation.get_language()
        if self.kwargs.get("lang", False):
            translation.activate(self.kwargs["lang"])

        try:
            content, subject, attachments = render_mail(template=template, html=True, preview=True)
        finally:
            translation.activate(old_language)

        context['content'] = content

        return super(MailPreview, self).render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super(MailPreview, self).get_context_data(**kwargs)
        context['preview'] = True
        return context


@require_superuser
def mail_template_test(request):
    if request.POST:
        form = MailTemplateTestForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            template = get_template(data['template'])

            old_language = translation.get_language()
            translation.activate(data['language'])

            html = data['format'] == 'html'

            mail_context = {'recipient': person_dict(request.person)}

            try:
                content, subject, attachments = render_mail(template=template, context=mail_context, html=html,
                                                            preview=True)
            finally:
                translation.activate(old_language)

            context = {'content': content}

            if html:
                return render(request, 'weekmail/weekmail_preview.html', context)
    else:
        form = MailTemplateTestForm()

    return render(request, 'tools_mailtemplatetest.html', locals())


class DataExportStatistics(RequireBoardMixin, ListView):
    model = DataExportInformation
    template_name = "data_export_statistics.html"
    paginate_by = 100
    ordering = '-id'

    def get_queryset(self):
        qs = self.model.objects.all()
        export_type = self.request.GET.get('export_type', '')

        if export_type:
            qs = qs.filter(export_type=export_type)

        return qs.order_by(self.ordering)

    def get_context_data(self, **kwargs):
        context = super(DataExportStatistics, self).get_context_data(**kwargs)
        context['model'] = self.model
        context['export_types_form'] = ExportTypeSelectForm(self.request.GET)
        return context


@method_decorator(csrf_exempt, name='dispatch')
class DocumensoWebhookView(RequireAllowlistedIPMixin, View):
    """
    Receives a POST request from Documenso containing a JSON event body.
    See: https://docs.documenso.com/docs/developers/webhooks/events for payload details

    This request must come from a whitelisted IP in the DOCUMENSO_SETTINGS['ALLOWED_WEBHOOK_IPS'] setting.
    The secret in the X-Documenso-Secret header must match the one in the DOCUMENSO_SETTINGS['WEBHOOK_SECRET'] setting.

    The view should always respond with a "200 OK" status, '{"received": true}' JSON body to confirm.
    """
    http_method_names = ['post']
    needs_login = False
    errors_as_json = True
    allowlisted_ip_addresses = settings.DOCUMENSO_SETTINGS.get('ALLOWED_WEBHOOK_IPS', [])
    allow_superusers = False

    def process_webhook(self, data):
        log = logging.getLogger("amelie.tools.views.DocumensoWebhookView")
        event = data.get("event")
        if event == "DOCUMENT_COMPLETED":
            envelope_id = data.get("payload", {}).get("envelopeId")
            external_id = data.get("payload", {}).get("externalId", "")

            # Parse the external ID
            external_match = AMELIE_REFERENCE_REGEX.match(external_id)
            if not external_match:
                if external_id.startswith("AML:"):
                    # It is something we could have known of, but it's unparseable.
                    log.warning(f"Received DOCUMENT_COMPLETE with external id '{external_id}', but it could not be parsed. Can't continue processing.")
                else:
                    # Nothing we know of, let's make a log of it and professionally ignore it.
                    log.warning(f"Received DOCUMENT_COMPLETE webhook from Documenso for an unknown document, ignoring. "
                                f"(externalId='{external_id}', envelopeId='{envelope_id}')")
                    log.debug("Unknown webhook contents:")
                    log.debug(json.dumps(data, indent=2))
                return
            external_id_parts = external_match.groupdict()

            # What kind of document just got signed, is it one of ours?
            if external_id_parts.get('type') == Membership.DOCUMENT_TYPE_ID:
                # Yup, it's a membership signature we sent
                log.info(f"Received DOCUMENT_COMPLETE webhook for Membership #{external_id_parts.get('id')}")
                # Try to find the Membership this was for
                try:
                    membership = Membership.objects.get(documenso_id=envelope_id)
                    # Save the document to the membership
                    membership.process_signed_document()
                except Membership.DoesNotExist:
                    log.warning(f"Could not find a membership that is waiting for a signature from envelope_id={envelope_id}. Stopping processing.")

            elif external_id_parts.get('type') == Authorization.DOCUMENT_TYPE_ID:
                # Yup, it's a mandate signature we sent
                log.info(f"Received DOCUMENT_COMPLETE webhook for Authorization #{external_id_parts.get('id')}")
                # Try to find the Authorization this was for
                try:
                    authorization = Authorization.objects.get(documenso_id=envelope_id)
                    # Save the document to the authorization
                    authorization.process_signed_document()
                except Authorization.DoesNotExist:
                    log.warning(f"Could not find an authorization that is waiting for a signature from envelope_id={envelope_id}. Stopping processing.")

            elif external_id_parts.get('type') == UnverifiedEnrollment.DOCUMENT_TYPE_ID:
                # Yup, it's an unverified enrollment form signature package we sent
                log.info(f"Received DOCUMENT_COMPLETE webhook for UnverifiedEnrollment #{external_id_parts.get('id')} with Authorization(s)#{external_id_parts.get('ids')}")
                # Try to find the UnverifiedEnrollment this was for
                try:
                    unverified_enrollment = UnverifiedEnrollment.objects.get(documenso_id=envelope_id)
                    # Save the document to the authorization
                    unverified_enrollment.process_signed_document()
                    # Delete the unverified enrollment (it is activated during the processing)
                    unverified_enrollment.delete()
                except UnverifiedEnrollment.DoesNotExist:
                    log.warning(f"Could not find an unverified enrollment that is waiting for a signature from envelope_id={envelope_id}. Stopping processing.")

            elif external_id_parts.get('type') == Person.DOCUMENT_TYPE_ID:
                # Yup, it's a regular enrollment form signature package we sent
                log.info(f"Received DOCUMENT_COMPLETE webhook for Enrollment for Membership #{external_id_parts.get('id')} with Authorization(s)#{external_id_parts.get('ids')}")
                # These are the hardest because there's not a single object to map to.
                # The best we can do is pass it on to another processing function
                Person.process_member_enrollment_signed_document(documenso_id=envelope_id)

            else:
                # Nothing we know of, let's make a log of it and professionally ignore it.
                log.warning(f"Received DOCUMENT_COMPLETE webhook from Documenso for an unknown document, ignoring. "
                            f"(externalId='{external_id}', envelopeId='{envelope_id}')")
                log.debug("Unknown webhook contents:")
                log.debug(json.dumps(data, indent=2))


    def post(self, request):
        log = logging.getLogger("amelie.tools.views.DocumensoWebhookView")

        ##
        # Verify request and get the JSON body
        ##
        # Settings for alexia age check API must be configured
        if settings.DOCUMENSO_SETTINGS.get('WEBHOOK_SECRET', None) is None or \
                settings.DOCUMENSO_SETTINGS.get('ALLOWED_WEBHOOK_IPS', None) is None:
            log.error("Documenso Webhook config missing from settings.")
            return HttpJSONResponse({"error": True}, status=500)

        # Must be POST request
        if request.method != "POST":
            log.error(f"Bad request, request method is {request.method}, not POST.")
            return HttpJSONResponse({"error": True}, status=400)

        # Headers must contain 'X-Documenso-Secret', and the value must match the setting
        secret_header = request.headers.get("X-Documenso-Secret", None)
        secret_setting = settings.DOCUMENSO_SETTINGS.get("WEBHOOK_SECRET", None)
        if secret_header is not None and secret_header != secret_setting:
            log.error(f"Bad request, missing or invalid webhook secret.")
            return HttpJSONResponse({"error": True}, status=400)

        # Must contain JSON body
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as e:
            log.error(f"Bad request, JSON decoding failed - {e}.")
            return HttpJSONResponse({"error": True}, status=400)

        # Access verified. Process the webhook content.
        self.process_webhook(body)

        # Return a 200 OK
        return HttpJSONResponse({"received": True})

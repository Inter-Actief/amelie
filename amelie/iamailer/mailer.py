import logging
import os
import time
from email.mime.image import MIMEImage
from hashlib import md5

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import get_connection
from django.template import Template
from django.template.context import Context
from django.template.loader import get_template
from django.utils import translation

from django.template.base import Template as ContextTemplate
from django.template.backends.django import Template as DictTemplate

from amelie.iamailer.message import EmailMultiAlternativesRelated

logger = logging.getLogger(__name__)

RESERVED_CONTEXT_VARS = ['render_preview', 'render_type', 'subject', 'attach_static']


def render_mail(template, context=None, html=False, preview=False):
    """
    Render an email template.
    :param template: Template object.
    :param context: Dict with context for template.
    :param html: Render HTML version. False renders plain text version.
    :param preview: Render preview for view in browser.
    :return: Tuple containing the rendered content, the subject for the mail and a list of attachments.
    """
    if not context:
        context = {}

    for reserved_var in RESERVED_CONTEXT_VARS:
        if reserved_var in context:
            raise ValueError('Reserved key {} not allowed in email context'.format(reserved_var))

    new_context = dict(context)
    new_context['render_preview'] = preview
    new_context['render_type'] = 'text/html' if html else 'text/plain'
    new_context['subject'] = None
    new_context['attach_static'] = {}

    # Django template base Templates need a Context() as context, but other Templates need a dict.
    # If we don't know the type, assume dict, as that has worked most of the time in the past.
    if type(template) == ContextTemplate:
        new_context = Context(new_context)
    elif type(template) == DictTemplate:
        new_context = dict(new_context)
    else:
        new_context = dict(new_context)

    content = template.render(new_context)

    subject = new_context.get('subject', None)
    attach_static = new_context.get('attach_static', {})
    attachments = _process_attach_static(attach_static)

    return content, subject, attachments


def _process_attach_static(attach_static):
    """
    Process attachments from template render.

    :param attach_static: dict containing attachments: {'cid': 'staticfilename'}
    :return: List of MIMEImage objects
    """
    attachments = []

    for cid, staticfilename in attach_static.items():
        fullpath = finders.find(staticfilename)
        basename = os.path.basename(staticfilename)

        if not fullpath:
            raise ValueError("Static file {} could not be found.".format(staticfilename))

        if cid != md5(staticfilename.encode()).hexdigest():
            raise ValueError("CID {} invalid for static file {}.".format(cid, staticfilename))

        with open(fullpath, 'rb') as imagefile:
            imagedata = imagefile.read()
        attachment = MIMEImage(imagedata, name=basename)
        attachment.add_header('Content-ID', '<{}>'.format(cid))
        attachment.add_header('Content-Disposition', 'inline', filename=basename)
        attachments.append(attachment)

    return attachments


def _send_mail_from_template(template, from_=None, to=None, cc=None, bcc=None, headers=None, context=None,
                             language=None, attachments=None, connection=None):
    """
    Send HTML mail to specified recipients by rendering template.
    :param template: Template to render.
    :param from_: From address.
    :param to: To addresses.
    :param cc: CC addresses.
    :param bcc: BCC addresses.
    :param headers: Dict containing headers.
    :param context: Dict containing context for template.
    :param language: Language code for translation.
    :param attachments: Attachments. List of tuples for parameters for EmailMultiAlternativesRelated.attach
    :param connection: Email backend connection.
    """
    # Remember the old translation setting
    old_language = translation.get_language()
    if language:
        translation.activate(language)

    # Render the template
    try:
        plain_content, plain_subject, plain_attachments = render_mail(template, context)
        html_content, html_subject, html_attachments = render_mail(template, context, html=True)
    finally:
        # Reactivate the old language
        translation.activate(old_language)

    subject = html_subject or plain_subject
    if not subject:
        raise ValueError('No subject defined for mail')

    # Override the to field and clear the cc and bcc fields if the global email intercept is set.
    if settings.EMAIL_INTERCEPT_ADDRESS is not None:
        if isinstance(settings.EMAIL_INTERCEPT_ADDRESS, list):
            to = settings.EMAIL_INTERCEPT_ADDRESS
        else:
            to = [settings.EMAIL_INTERCEPT_ADDRESS]
        cc = None
        bcc = None

    # Build the email message
    if not headers:
        headers = {}
    if 'Return-Path' not in headers:
        headers['Return-Path'] = settings.EMAIL_RETURN_PATH

    message = EmailMultiAlternativesRelated(subject, plain_content, from_, to, cc=cc, bcc=bcc, connection=connection,
                                            headers=headers)
    message.attach_alternative(html_content, "text/html")
    for html_attachment in html_attachments:
        message.attach_related(html_attachment)

    if attachments:
        for attachment in attachments:
            message.attach(*attachment)

    # Send the email message
    return message.send()


def send_mails_from_template(mails, from_=None, template_name=None, template_string=None, report_to=None,
                             report_language=None, report_always=True):
    """
    Send HTML mails to specified recipients by rendering template.

    Exactly one of parameters template_name or template_string must be provided.

    :param mails: Dict containing email information:
        {
            'to': ['Recipient <recipient@example.com>'],
            'cc': ['Carbon copy <cc@example.com>'],
            'bcc': ['Blind carbon copy <bcc@example.com>'],
            'headers': {'Header': 'Value'},
            'context': {'key': 'value'},
            'language': 'nl',
            'attachments': [('filename.txt', 'content', 'text/plain')]
        }
    :param from_: From address. Example: 'Sender <sender@example.com>'
    :param template_name: Name of template file to render.
    :param template_string: Template string to render.
    :param report_to: Address to send delivery report to. None of no delivery report must be send.
                      Example: 'Sender <sender@example.com>'
    :param report_language: Language code for translations.
    :param report_always: Always send a delivery report. If False, only delivery reports are send if an error occures.
    :return: Tuple with the number of sent mails and mails with errors.
    """

    sent_count = 0
    error_count = 0

    if not template_string and not template_name:
        raise ValueError('None of template and template_name are provided')
    if template_string and template_name:
        raise ValueError('Both template and template_name are provided')

    if template_name:
        template = get_template(template_name)
    else:
        template = Template(template_string)

    logger.info('Sending mails to {} recipients'.format(len(mails)))

    # Get SMTP connection
    connection = get_connection(timeout=settings.EMAIL_TIMEOUT)

    mails_failed = []

    # Send mails
    for maildata in mails:
        to = maildata['to']
        cc = maildata.get('cc', [])
        bcc = maildata.get('bcc', [])
        headers = maildata.get('headers', {})
        context = maildata.get('context', {})
        language = maildata.get('language', None)
        attachments = maildata.get('attachments', None)

        to_string = ';'.join(to)
        logger.debug('Sending mail to {}'.format(to_string))

        try:
            _send_mail_from_template(template=template, from_=from_, to=to, cc=cc, bcc=bcc, headers=headers,
                                     context=context, language=language, attachments=attachments, connection=connection)
        except Exception as e:
            error_count += 1
            logger.exception('Sending mail to {} failed'.format(to_string))
            mails_failed.append({
                'maildata': maildata,
                'exception': e,
            })
        else:
            logger.debug('Sending mail to {} succeeded'.format(to_string))
            sent_count += 1

        # Sleep between sending mails
        time.sleep(settings.EMAIL_DELAY)

    if error_count == 0 and sent_count > 0:
        logger.info('Sending {} mails succeeded'.format(sent_count))
    else:
        logger.warning('Sending {} mails succeeded, {} errors reported'.format(sent_count, error_count))

    # Send delivery report
    if report_to and (report_always or error_count):
        # noinspection PyBroadException
        try:
            report_context = {
                'from': from_,
                'mails': mails,
                'sent_count': sent_count,
                'error_count': error_count,
                'mails_failed': mails_failed,
            }
            report_template = get_template("iamailer/report.mail")

            _send_mail_from_template(template=report_template, to=[report_to, ], context=report_context,
                                     language=report_language, connection=connection)

            logger.debug('Sending delivery report succeeded')
        except Exception:
            logger.exception('Sending delivery report failed')

    # Done
    return sent_count, error_count

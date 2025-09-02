import logging
import time

from celery import shared_task, group, chord
from django.conf import settings
from django.core.mail import get_connection
from django.template import Template
from django.template.loader import get_template

from amelie.iamailer.mailer import send_single_mail_from_template


@shared_task(name="iamailer.send_mails")
def send_mails(mails, mail_from=None, template_name=None, template_string=None, report_to=None, report_language=None,
               report_always=True):
    """
    Send HTML mails to specified recipients by rendering template.

    Exactly one of parameters template_name or template_string must be provided.

    This task will create and launch a Celery workflow with a new Task for each mail that needs to be sent,
    followed by a single task to send the delivery report mail.

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
    :param mail_from: From address. Example: 'Sender <sender@example.com>'
    :param template_name: Name of template file to render.
    :param template_string: Template string to render.
    :param report_to: Address to send delivery report to. None of no delivery report must be sent.
                      Example: 'Sender <sender@example.com>'
    :param report_language: Language code for translations.
    :param report_always: Always send a delivery report. If False, only delivery reports are send if an error occures.
    :return: Tuple with the number of sent mails and mails with errors.
    """
    logger = logging.getLogger(__name__)

    if not template_string and not template_name:
        raise ValueError('None of template and template_name are provided')
    if template_string and template_name:
        raise ValueError('Both template and template_name are provided')

    if template_name:
        template = get_template(template_name)
    else:
        template = Template(template_string)

    logger.info('Sending mails to {} recipients'.format(len(mails)))

    # Build a Celery workflow that will send all the mails and then send a delivery report
    chord(
        # Send each mail,
        group(send_single_mail.s(template=template, mail_from=mail_from, maildata=maildata) for maildata in mails),
        # followed by the delivery report,
        send_delivery_report.s(
            mail_from=mail_from, total_mail_count=len(mails), report_to=report_to,
            report_language=report_language, report_always=report_always
        )
    ).delay()  # And execute the workflow (the last two brackets)


# acks_late makes it so that the task is retried if the worker crashes before it finishes.
@shared_task(name="iamailer.send_single_mail", acks_late=True)
def send_single_mail(template, mail_from, maildata):
    """
    Execute an exporter for a given Person and ApplicationStatus
    :param template: The mail as a Template object.
    :param mail_from: Sender information for mail From header.
    :param maildata: Dictionary of Mail data, as returned by IAMailer's `Recipient.get_maildata()`.
    :return: Dictionary with data about the sending:
             {
               'to': maildata.to (Name/email where the mail was sent to),
               'success': bool,
               'exception': exception string if not successful else None
             }
    """
    logger = logging.getLogger(__name__)
    to = maildata['to']
    cc = maildata.get('cc', [])
    bcc = maildata.get('bcc', [])
    headers = maildata.get('headers', {})
    context = maildata.get('context', {})
    language = maildata.get('language', None)
    attachments = maildata.get('attachments', None)

    to_string = ';'.join(to)
    logger.debug('Sending mail to {}'.format(to_string))


    success = True
    exception = None
    # noinspection PyBroadException
    try:
        # Send mail
        send_single_mail_from_template(
            template=template, mail_from=mail_from, to=to, cc=cc, bcc=bcc, headers=headers,
            context=context, language=language, attachments=attachments,
            connection=get_connection(timeout=settings.EMAIL_TIMEOUT))
    except Exception as e:
        success = False
        exception = str(e)
        logger.exception('Sending mail to {} failed'.format(to_string))
    else:
        logger.debug('Sending mail to {} succeeded'.format(to_string))

    # Sleep between sending mails
    time.sleep(settings.EMAIL_DELAY)

    return {
        'to': maildata['to'],
        'success': success,
        'exception': exception
    }


# acks_late makes it so that the task is retried if the worker crashes before it finishes.
@shared_task(name="iamailer.send_delivery_report", acks_late=True)
def send_delivery_report(results, mail_from, total_mail_count, report_to, report_language, report_always):
    logger = logging.getLogger(__name__)


    # If the person sent only one mail, results will be a single dict, if they sent more than one,
    # it will be al list. Convert the dict into a 1-long list if it is a dict to avoid problems.
    if type(results) == dict:
        results = [results]

    # Collect the errors and count the errors and successes
    failed_mails = [r for r in results if not r['success']]
    error_count = len(failed_mails)
    sent_count = len(results) - error_count


    if error_count == 0 and sent_count > 0:
        logger.info('Sending {} mails succeeded'.format(sent_count))
    else:
        logger.warning('Sending {} mails succeeded, {} errors reported'.format(sent_count, error_count))

    # Send delivery report
    if report_to and (report_always or error_count):
        # noinspection PyBroadException
        try:
            # Send report
            send_single_mail_from_template(
                template=get_template("iamailer/report.mail"),
                to=[report_to],
                context={
                    'from': mail_from,
                    'mail_count': total_mail_count,
                    'sent_count': sent_count,
                    'error_count': error_count,
                    'mails_failed': failed_mails,
                },
                language=report_language,
                connection=get_connection(timeout=settings.EMAIL_TIMEOUT)
            )
            logger.debug('Sending delivery report succeeded')
        except Exception:
            logger.exception('Sending delivery report failed')

import logging
import time

from celery import shared_task, group, chord
from django.conf import settings
from django.core.mail import get_connection
from django.template import Template
from django.template.loader import get_template

from amelie.iamailer.mailer import send_single_mail_from_template


logger = logging.getLogger(__name__)


@shared_task(name="iamailer.send_mails")
def send_mails(mails, mail_from=None, template_name=None, template_string=None, report_to=None, report_language=None,
               report_always=True):
    """
    Send HTML mails to specified recipients by rendering a template.

    Exactly one of the parameters template_name or template_string must be provided.

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
    :param template_name: Name of the template file to render.
    :param template_string: Template string to render.
    :param report_to: Address to send the delivery report to. None if no delivery report must be sent.
                      Example: 'Sender <sender@example.com>'
    :param report_language: Language code for translations.
    :param report_always: Always send a delivery report. If False, only delivery reports are sent if an error occurs.

    :return: Dictionary with the number of tasks scheduled:
             {
               'scheduled_tasks': The number of mail tasks scheduled.
             }
    """
    num_mails = len(mails)
    logger.debug(f'IAMailer task to schedule {num_mails} mails started.')

    if not template_string and not template_name:
        raise ValueError('None of template and template_name are provided')
    if template_string and template_name:
        raise ValueError('Both template and template_name are provided')

    # Verify that the template exists/works by trying to load it.
    logger.debug('Loading template...')
    if template_name:
        _ = get_template(template_name)
        logger.debug("Using template from file '{}'".format(template_name))
    else:
        _ = Template(template_string)
        logger.debug('Using template from string')

    # Build a Celery workflow that will send all the mails and then send a delivery report
    logger.info('Sending mails to {} recipients'.format(num_mails))
    chord(
        # Send each mail,
        group(send_single_mail.s(mail_from=mail_from, maildata=maildata, template_name=template_name, template_string=template_string) for maildata in mails),
        # followed by the delivery report,
        send_delivery_report.s(
            mail_from=mail_from, total_mail_count=num_mails, report_to=report_to,
            report_language=report_language, report_always=report_always
        )
    ).delay()  # And execute the workflow (the last `.delay()`)
    logger.info(f'{num_mails} IAMailer tasks scheduled and started.')
    return {'scheduled_tasks': num_mails}


# acks_late makes it so that the task is retried if the worker crashes before it finishes.
@shared_task(name="iamailer.send_single_mail", acks_late=True)
def send_single_mail(mail_from, maildata, template_name=None, template_string=None):
    """
    Send a single e-mail.

    :param mail_from: Sender information for mail From header.
    :param maildata: Dictionary of Mail data, as returned by IAMailer's `Recipient.get_maildata()`.
    :param template_name: The name of the template file to use (only if template_string is not provided).
    :param template_string: The template string to use (only if template_name is not provided).
    :return: Dictionary with data about the sending:
             {
               'to': maildata.to (Name/email where the mail was sent to),
               'success': bool,
               'exception': exception string if not successful else None
             }
    """
    to = maildata['to']
    to_string = ';'.join(to)
    cc = maildata.get('cc', [])
    bcc = maildata.get('bcc', [])
    headers = maildata.get('headers', {})
    context = maildata.get('context', {})
    language = maildata.get('language', None)
    attachments = maildata.get('attachments', None)

    success = True
    exception = None
    # noinspection PyBroadException
    try:
        if not template_string and not template_name:
            raise ValueError('None of template and template_name are provided')
        if template_string and template_name:
            raise ValueError('Both template and template_name are provided')

        if template_name:
            template = get_template(template_name)
        else:
            template = Template(template_string)

        logger.debug(f'Sending mail to {to_string}')

        # Send mail
        send_single_mail_from_template(
            template=template, mail_from=mail_from, to=to, cc=cc, bcc=bcc, headers=headers,
            context=context, language=language, attachments=attachments,
            connection=get_connection(timeout=settings.EMAIL_TIMEOUT))
    except Exception as e:
        success = False
        exception = str(e)
        logger.exception(f'Sending mail to {to_string} failed')
    else:
        logger.info(f'Sending mail to {to_string} succeeded')

    # Sleep between sending mails
    logger.debug(f'Waiting for e-mail delay ({settings.EMAIL_DELAY} seconds) before finishing task...')
    time.sleep(settings.EMAIL_DELAY)

    return {
        'to': maildata['to'],
        'success': success,
        'exception': exception
    }


# acks_late makes it so that the task is retried if the worker crashes before it finishes.
@shared_task(name="iamailer.send_delivery_report", acks_late=True)
def send_delivery_report(results, mail_from, total_mail_count, report_to, report_language, report_always):
    """
    Send a delivery report based on the number of successfully and unsuccessfully sent emails.

    :param results: List of Celery Task results from the `send_single_mail` tasks.
    :param mail_from: From address. Example: 'Sender <sender@example.com>'
    :param total_mail_count: Total number of e-mails that were attempted.
    :param report_to: Address to send the delivery report to. None if no delivery report must be sent.
                      Example: 'Sender <sender@example.com>'
    :param report_language: Language code for translations.
    :param report_always: Always send a delivery report. If False, only delivery reports are sent if an error occurs.

    :return: Dictionary with data about the results:
             {
               'num_total': Total number of e-mails that were attempted
               'num_success': Number of successfully sent emails
               'num_failed': Number of unsuccessfully sent emails
             }
    """

    logger.debug(f'Sending delivery report to {report_to}...')
    # If the person sent only one mail, the results will be a single dict, if they sent more than one,
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

    # Send the delivery report
    if report_to and (report_always or error_count):
        # noinspection PyBroadException
        try:
            # Send the report
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

    return {
        'num_total': total_mail_count,
        'num_success': sent_count,
        'num_failed': error_count
    }

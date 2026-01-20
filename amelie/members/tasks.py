import logging

from celery import shared_task
from django.template import Template, Context

from amelie.api.models import PushNotification
from amelie.api.push_utils import send_basic_notification
from amelie.iamailer import MailTask, Recipient
from amelie.tools.const import TaskPriority
from amelie.members.models import Preference


logger = logging.getLogger(__name__)


@shared_task(name="default.send_push_notification")
def send_push_notification(notification: PushNotification, recipients, report_to=None, report_language=None):
    logger.debug(f"Sending push notification to {len(recipients)} recipients.")
    preferences = Preference.objects.filter(name='notifications')

    # Split filtered recipients based on their preferences and connected push devices
    recipients = recipients.filter(preferences__in=preferences, user__fcmdevice__isnull=False).distinct()

    # Initialize the list values to include in the mailing
    successful_push_recipients = []
    failed_notification_recipients = []

    for recipient in recipients:
        # Render an English and Dutch message variant based on the template tags using the context renderer
        message_en = Template(notification.message_en).render(Context({'recipient': recipient}))
        message_nl = Template(notification.message_nl).render(Context({'recipient': recipient}))

        # Create a push notification object based on recipient information
        personal_notification = PushNotification(title_en=notification.title_en, title_nl=notification.title_nl,
                                                 message_en=message_en, message_nl=message_nl)

        # Attempt to send a push notification
        try:
            fcm_result = send_basic_notification(personal_notification, [recipient])
            fcm_result = [x for x in fcm_result if x is not None]
        except Exception as e:
            fcm_result = []

        # If the push notification was successful, add the recipient to the list of successful push recipients
        if any([res['success'] == 1 for res in fcm_result]):
            successful_push_recipients.append(recipient)
        else:
            failed_notification_recipients.append(recipient)

    logger.info(f"Notifications sent. {len(successful_push_recipients)} successful and {len(failed_notification_recipients)} failed.")

    # Send a report mail to the requester
    if report_to is not None:
        logger.debug(f"Sending push report...")
        mail_task = MailTask(template_name='tools/push_report.mail', priority=TaskPriority.LOW)

        # Render an English and Dutch message variant based on the template tags using the context renderer
        message_en = Template(notification.message_en).render(Context({'recipient': recipients[0]}))
        message_nl = Template(notification.message_nl).render(Context({'recipient': recipients[0]}))

        # Create a push notification object based on recipient information
        mail_notification = PushNotification(title_en=notification.title_en, title_nl=notification.title_nl,
                                             message_en=message_en, message_nl=message_nl)

        report_context = {
            'notification': mail_notification,
            'recipients': len(recipients),
            'successful_push_recipients': len(successful_push_recipients),
            'failed_notification_recipients': [
                {
                    'full_name': recipient.full_name,
                } for recipient in failed_notification_recipients
            ]
        }

        mail_task.add_recipient(Recipient(
            tos=[report_to],
            context=report_context,
            language=report_language,
        ))

        mail_task.send()
        logger.debug(f"Push report mail sent.")

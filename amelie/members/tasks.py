from celery.task import task
from django.template import Template, Context

from amelie.api.models import PushNotification
from amelie.api.push_utils import send_basic_notification
from amelie.iamailer import MailTask, Recipient
from amelie.members.models import Preference


@task()
def send_push_notification(notification: PushNotification, recipients, report_to=None, report_language=None):
    preferences = Preference.objects.filter(name='notifications')

    # Split filtered recipients based on whether their preferences and connected push devices
    recipients = recipients.filter(preferences__in=preferences, user__fcmdevice__isnull=False).distinct()

    # Initialize the list values to include in the mailing
    successful_push_recipients = []
    failed_notification_recipients = []

    for recipient in recipients:
        # Render a English and Dutch message variants based on the template tags using the context renderer
        message_en = Template(notification.message_en).render(Context({'recipient': recipient}))
        message_nl = Template(notification.message_nl).render(Context({'recipient': recipient}))

        # Create a push notification object based on recipient information
        personal_notification = PushNotification(title_en=notification.title_en, title_nl=notification.title_nl,
                                                 message_en=message_en, message_nl=message_nl)

        # Attempt to send a push notification
        fcm_result = send_basic_notification(personal_notification, [recipient])
        fcm_result = [x for x in fcm_result if x is not None]

        # If the push notification was successful, add the recipient to the list of successful push recipients
        if any([res['success'] == 1 for res in fcm_result]):
            successful_push_recipients.append(recipient)
        else:
            failed_notification_recipients.append(recipient)

    # Send a mailing to the requester
    if report_to is not None:
        mail_task = MailTask(template_name='tools/push_report.mail')

        # Render a English and Dutch message variants based on the template tags using the context renderer
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

        mail_task.send(delay=False)

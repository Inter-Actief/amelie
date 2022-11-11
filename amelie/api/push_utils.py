import json

from fcm_django.fcm import fcm_send_topic_message
from fcm_django.models import FCMDevice

from amelie.settings import PUSH_TOPICS, LANGUAGES


def send_basic_notification(notification, recipients=None):
    # Retrieve all FCM-registered devices
    devices = FCMDevice.objects.filter(active=True)

    # If the recipients are specifically defined, filter the devices based on the passed recipients
    if recipients is not None:
        devices = devices.filter(user__person__in=recipients)

    result = []

    # Convert JSON Data
    json_data = {}
    if notification.json_data is not None:
        json_data = notification.json_data
    json_data['push_id'] = notification.id

    # Send a push notification to devices based on their preferred language
    for loc, val in LANGUAGES:
        loc_devices = devices.filter(user__person__preferred_language=loc)
        result.append(loc_devices.send_message(title=getattr(notification, 'title_{}'.format(loc)),
                                               body=getattr(notification, 'message_{}'.format(loc)),
                                               data=json_data))

    return result


def send_topic_notification(notification, topic):
    # Convert JSON Data
    json_data = {}
    if notification.json_data is not None:
        json_data = notification.json_data
    json_data['push_id'] = notification.id

    if topic in PUSH_TOPICS:
        for loc, val in LANGUAGES:
            loc_topic = '{}_{}'.format(topic, loc)
            fcm_send_topic_message(topic_name=loc_topic,
                                   message_title=getattr(notification, 'title_{}'.format(loc)),
                                   message_body=getattr(notification, 'message_{}'.format(loc)),
                                   data_message=json_data)

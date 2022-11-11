import logging

import requests
from celery.task import task

logger = logging.getLogger(__name__)


@task
def send_participation_callback(event_id, person_id, action):

    from amelie.calendar.models import Event
    from amelie.members.models import Person

    event = Event.objects.get(id=event_id)
    person = Person.objects.get(id=person_id)

    if not event.callback_url:
        return

    try:
        r = requests.post(event.callback_url, data={
            'secret_key': event.callback_secret_key,
            'action': action,
            'email': person.email_address,
            'name': person.incomplete_name()
        })
        if r.status_code != 200:
            logger.exception("Calling callback url for event ")
    except requests.exceptions.RequestException as e:
        logger.exception("Calling callback url for event failed")
        pass

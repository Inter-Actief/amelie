# -*- coding: utf-8 -*-
from datetime import timedelta, datetime

import hashlib
import icalendar
from copy import deepcopy
from django.conf import settings
from django.utils.encoding import force_str
from django.utils.translation import gettext as _, get_language
from pytz import timezone


def ical_event(event):
    evt = icalendar.Event()

    class_hash = hashlib.sha256((event['__module__'] + "." + event['__class__'].__name__).encode()).hexdigest()
    event_id_hash = hashlib.sha256(str(event['id']).encode()).hexdigest()
    evt['uid'] = class_hash + event_id_hash + "@www.inter-actief.utwente.nl"

    evt.add('dtstamp', event['begin'])
    evt.add('dtstart', event['begin'])
    evt.add('sequence', event['update_count'])

    if "end" in event or "end" in event:
        evt.add('dtend', event['end'] if 'end' in event else event['end'])

    if "summary_override" in event:
        evt.add('summary', event['summary_override'])
    elif "summary" in event and event['summary']:
        evt.add('summary', event['summary'])

    if "description" in event and event['description']:
        evt.add('description', event['description'])

    if "location" in event and event['location']:
        evt.add('location', event['location'])

    if "organizer_email" in event and "organizer_name" in event \
            and event['organizer_email'] and event["organizer_name"]:
        evt.add('organizer', 'MAILTO:%s' % event['organizer_email'], parameters={'CN': event['organizer_name'], })

    if 'get_absolute_url' in event:
        base_url = settings.ABSOLUTE_PATH_TO_SITE
        evt.add('url', '{}{}'.format(base_url, event['get_absolute_url']()))

    return evt


def ical_calendar(calendar, events=None, max_duration_before_split=timedelta(days=3)):
    if events is None:
        events = []

    cal = icalendar.Calendar()

    cal.add('version', '2.0')
    cal.add('prodid', '-//inter-actief//amélie//NL')
    cal.add('x-wr-calname', force_str(calendar))
    # lines.append(Line('CALSCALE', 'GREGORIAN'))

    local_tz = timezone(settings.TIME_ZONE)

    # get two
    daylight, standard = [(dt, local_tz._transition_info[num]) for num, dt in enumerate(local_tz._utc_transition_times) if dt.year == datetime.today().year]

    timezone_daylight = icalendar.TimezoneDaylight()
    timezone_daylight.add('TZOFFSETFROM', standard[1][0])
    timezone_daylight.add('TZOFFSETTO', daylight[1][0])
    timezone_daylight.add('TZNAME', daylight[1][2])
    timezone_daylight.add('DTSTART', daylight[0])
    timezone_daylight.add('rrule', {'freq': 'yearly', 'bymonth': 3, 'byday': '-1su'})

    timezone_standard = icalendar.TimezoneStandard()
    timezone_standard.add('TZOFFSETFROM', daylight[1][0])
    timezone_standard.add('TZOFFSETTO', standard[1][0])
    timezone_standard.add('TZNAME', standard[1][2])
    timezone_standard.add('DTSTART', standard[0])
    timezone_standard.add('rrule', {'freq': 'yearly', 'bymonth': 10, 'byday': '-1su'})

    cal_tz = icalendar.Timezone()
    cal_tz.add('tzid', local_tz)
    cal_tz.add('X-LIC-LOCATION', local_tz)
    cal_tz.add_component(timezone_daylight)
    cal_tz.add_component(timezone_standard)
    cal.add_component(cal_tz)

    for event in events:
        # Make a dictionary of the event so that we don't accidentally alter the model instance that might get saved
        event_dict = event.__dict__
        event_dict['__module__'] = event.__module__
        event_dict['__class__'] = event.__class__
        if hasattr(event, "organizer") and event.organizer is not None:
            event_dict['organizer_name'] = event.organizer.name
            event_dict['organizer_email'] = event.organizer.email
        if event.summary:
            event_dict['summary'] = event.summary
        if event.description:
            event_dict['description'] = event.description

        # Fix description and summary fields in the dict if they don't exist
        language = get_language()
        keys = event_dict.keys()
        if 'description' not in keys:
            if 'description_en' not in keys and 'description_nl' not in keys:
                event_dict['description'] = ""
            else:
                if language == "en" and event_dict['description_en']:
                    event_dict['description'] = event_dict['description_en']
                else:
                    event_dict['description'] = event_dict['description_nl']

        if 'summary' not in keys:
            if 'summary_en' not in keys and 'summary_nl' not in keys:
                event_dict['summary'] = ""
            else:
                if language == "en" and event_dict['summary_en']:
                    event_dict['summary'] = event_dict['summary_en']
                else:
                    event_dict['summary'] = event_dict['summary_nl']

        # Check duration of an event, if its longer then max_duration_before_split, split it into a start and end event.
        if event.end - event.begin >= max_duration_before_split:
            start_event = deepcopy(event_dict)
            # Remove the end date of this object to signal that this event is one day long ("all day event")
            del start_event['end']
            if 'summary' in start_event.keys():
                start_event['summary_override'] = _("[START] {}").format(start_event['summary'])

            cal.add_component(ical_event(start_event))

            end_event = deepcopy(event_dict)
            # The end event starts on the end of the total event
            end_event['begin'] = end_event['end']
            del end_event['end']
            if 'summary' in end_event.keys():
                end_event['summary_override'] = _("[END] {}").format(end_event['summary'])
            # The primary key of this event should be different from the start event, therefore we negate it to produce
            # a new digest
            end_event['id'] = -end_event['id']

            cal.add_component(ical_event(end_event))
        else:
            cal.add_component(ical_event(event_dict))

    return cal.to_ical()

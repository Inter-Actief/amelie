from django.utils import translation

from django.conf import settings
from amelie.iamailer import MailTask
from amelie.members.models import Preference
from amelie.tools.calendar import ical_calendar
from amelie.tools.mail import PersonRecipient


def activity_send_enrollmentmail(participation, from_waiting_list=False):
    """
    Send a confirmation of enrollment for an activity.

    Sends an ical-invite if this has been indicated through preferences.
    """

    # Generate an invite for the e-mail based on the preferences
    preference = Preference.objects.get(name__iexact='mail_send_invite')

    person = participation.person
    activity = participation.event

    current_language = translation.get_language()
    try:
        translation.activate(person.preferred_language)

        if person.has_preference(preference=preference):
            invite = True
            ical = ical_calendar(activity.summary, [activity, ]).decode()
            attachments = [('invite.ics', ical, 'text/calendar')]
        else:
            invite = False
            attachments = []

        template_name = "activities/activity_enrolled.mail"
        if from_waiting_list:
            template_name = "activities/activity_enrolled_from_waiting_list.mail"

        task = MailTask(from_=u'Inter-Activiteit <bestuur@inter-actief.net>',
                        template_name=template_name,
                        report_to=u'Inter-Activiteit <bestuur@inter-actief.net>', report_always=False)
        task.add_recipient(PersonRecipient(
            recipient=person,
            context={'activity': activity,
                     'enrolled_by': participation.added_by if participation.added_by != person else None,
                     'invite': invite,
                     'participation': participation,
                     },
            attachments=attachments,
        ))

        # Send e-mail
        task.send()
    finally:
        translation.activate(current_language)


def activity_send_cancellationmail(participants, activity, request, from_waiting_list=False):
    """
    Send a cancellation of enrollment for an activity.
    """

    template_name = "activities/activity_cancelled.mail"
    if from_waiting_list:
        template_name = "activities/activity_cancelled_from_waiting_list.mail"

    task = MailTask(template_name=template_name)

    # If debug is enabled, add a single recipient, the person themselves
    if settings.DEBUG:
        task.add_recipient(PersonRecipient(request.person, context={'activity': activity}))
    else:
        for person in participants:
            task.add_recipient(PersonRecipient(person, context={'activity': activity}))

    task.send()


def activity_send_on_waiting_listmail(participation):
    """
    Send a confirmation of enrollment on the waiting list for an activity.

    Sends an ical-invite if this has been indicated through preferences.
    """

    # Generate an invite for the e-mail based on the preferences
    preference = Preference.objects.get(name__iexact='mail_send_invite')

    person = participation.person
    activity = participation.event

    current_language = translation.get_language()
    try:
        translation.activate(person.preferred_language)

        if person.has_preference(preference=preference):
            invite = True
            ical = ical_calendar(f"[Waiting list] {activity.summary}", [activity, ]).decode()
            attachments = [('invite.ics', ical, 'text/calendar')]
        else:
            invite = False
            attachments = []

        task = MailTask(from_='Inter-Activiteit <bestuur@inter-actief.net>',
                        template_name='activities/activity_enrolled_on_waiting_list.mail',
                        report_to='Inter-Activiteit <bestuur@inter-actief.net>', report_always=False)
        task.add_recipient(PersonRecipient(
            recipient=person,
            context={'activity': activity,
                     'enrolled_by': participation.added_by if participation.added_by != person else None,
                     'invite': invite,
                     'participation': participation,
                     },
            attachments=attachments,
        ))

        # Send e-mail
        task.send()
    finally:
        translation.activate(current_language)

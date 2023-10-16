from django.utils import translation

from amelie.iamailer import MailTask
from amelie.members.models import Preference
from amelie.tools.calendar import ical_calendar
from amelie.tools.mail import PersonRecipient
from django.utils.translation import gettext_lazy as _


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

        task = MailTask(from_=_(u'Inter-Activity') + ' <bestuur@inter-actief.net>',
                        template_name=template_name,
                        report_to=_(u'Inter-Activity') + ' <bestuur@inter-actief.net>', report_always=False)
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
            ical = ical_calendar(f"[Waiting list] {activity.summary}", [
                                 activity, ]).decode()
            attachments = [('invite.ics', ical, 'text/calendar')]
        else:
            invite = False
            attachments = []

        task = MailTask(from_=_('Inter-Activity') + ' <bestuur@inter-actief.net>',
                        template_name='activities/activity_enrolled_on_waiting_list.mail',
                        report_to=_('Inter-Activity') + ' <bestuur@inter-actief.net>', report_always=False)
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

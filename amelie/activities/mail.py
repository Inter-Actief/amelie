from django.utils import translation

from django.conf import settings
from amelie.iamailer import MailTask, Recipient
from amelie.members.models import Preference
from amelie.tools.calendar import ical_calendar
from amelie.tools.mail import PersonRecipient
from django.utils.translation import gettext_lazy as _


def activity_send_cashrefundmail(cash_participants, activity, request):
    """
    Notify the treasurer that cash paying participants from a cancelled activity should get their money back.
    """

    # Send an email to the treasurer
    template_name = "activities/activity_cancelled_treasurer.mail"
    context = {
        "participants": [{
            "person": cash_participant.person,
            "costs": cash_participant.calculate_costs()[0],
        } for cash_participant in cash_participants],
        "activity": activity
    }
    task = MailTask(template_name=template_name)
    task.add_recipient(Recipient(
        tos=['Treasurer Inter-Actief <treasurer@inter-actief.net>'],
        context=context
    ))
    task.send()


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


def activity_send_cancellationmail(participants, activity, request, from_waiting_list=False):
    """
    Send a cancellation of enrollment for an activity.
    """

    template_name = "activities/activity_cancelled.mail"
    if from_waiting_list:
        template_name = "activities/activity_cancelled_from_waiting_list.mail"

    task = MailTask(template_name=template_name)
    for participant in participants:
        task.add_recipient(PersonRecipient(participant.person, context={
            'activity': activity,
            'participation_costs': participant.calculate_costs()[0],
            'paymentmethod': participant.get_payment_method_display()
        }))

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

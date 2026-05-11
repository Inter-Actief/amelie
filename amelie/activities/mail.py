from django.utils import translation

from amelie.calendar.models import Participation
from amelie.iamailer import MailTask, Recipient
from amelie.tools.const import TaskPriority
from amelie.members.models import Preference
from amelie.tools.calendar import ical_calendar
from amelie.tools.mail import PersonRecipient
from django.utils.translation import gettext_lazy as _l


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
    task = MailTask(template_name=template_name, priority=TaskPriority.HIGH)
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

        task = MailTask(
            from_=_l(u'Inter-Activity') + ' <bestuur@inter-actief.net>',
            template_name=template_name,
            report_to=_l(u'Inter-Activity') + ' <bestuur@inter-actief.net>',
            report_always=False,
            priority=TaskPriority.HIGH
        )
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


def activity_send_cancellationmail(participations, activity, from_waiting_list=False):
    """
    Send a cancellation of enrollment for an activity.
    """

    template_name = "activities/activity_cancelled.mail"
    if from_waiting_list:
        template_name = "activities/activity_cancelled_from_waiting_list.mail"

    task = MailTask(template_name=template_name, priority=TaskPriority.HIGH)
    for participation in participations:
        task.add_recipient(PersonRecipient(participation.person, context={
            'activity': activity,
            'participation_costs': participation.calculate_costs()[0],
            'paymentmethod': participation.get_payment_method_display()
        }))
    task.send()

def activity_send_price_change_mail(old_activity, new_activity):
    """
    Email all enrolled people to notify them of a price change
    """
    participations = old_activity.participation_set.filter(payment_method=Participation.PaymentMethodChoices.AUTHORIZATION)
    template_name = "activities/activity_price_change.mail"
    can_unenroll = new_activity.can_unenroll
    task = MailTask(template_name=template_name, priority=TaskPriority.HIGH)
    for participation in participations:
        task.add_recipient(PersonRecipient(participation.person, context={
            'activity': old_activity,
            'price_old': old_activity.price,
            'price_new': new_activity.price,
            'can_unenroll': can_unenroll,
            'participation_costs': participation.calculate_costs()[0],
            'on_waiting_list': participation.waiting_list
        }))
    task.send()


def activity_send_enrollment_option_price_change_mail(old_enrollment_option, new_enrollment_option):
    """
    Email all enrolled people to notify them of a price change
    """
    participations = new_enrollment_option.activity.participation_set.filter(payment_method=Participation.PaymentMethodChoices.AUTHORIZATION)
    template_name = "activities/activity_price_change.mail"
    can_unenroll = new_enrollment_option.activity.can_unenroll
    task = MailTask(template_name=template_name, priority=TaskPriority.HIGH)
    for participation in participations:
        task.add_recipient(PersonRecipient(participation.person, context={
            'activity': old_enrollment_option.activity,
            'enrollment_option': old_enrollment_option,
            'price_old': old_enrollment_option.price_extra,
            'price_new': new_enrollment_option.price_extra,
            'can_unenroll': can_unenroll,
            'participation_costs': participation.calculate_costs()[0],
            'on_waiting_list': participation.waiting_list
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
            ical = ical_calendar(f"[Waiting list] {activity.summary}", [activity]).decode()
            attachments = [('invite.ics', ical, 'text/calendar')]
        else:
            invite = False
            attachments = []

        task = MailTask(
            from_=_l('Inter-Activity') + ' <bestuur@inter-actief.net>',
            template_name='activities/activity_enrolled_on_waiting_list.mail',
            report_to=_l('Inter-Activity') + ' <bestuur@inter-actief.net>',
            report_always=False,
            priority=TaskPriority.HIGH
        )
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

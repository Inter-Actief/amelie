import locale
import threading
from contextlib import contextmanager

from django.contrib import messages
from django.db import transaction
from django.utils.translation import gettext as _

from amelie.activities.mail import activity_send_enrollmentmail
from amelie.calendar.models import Participation


def check_enrollment_allowed(request, activity, person=None, indirect=False, ignore_full=False,
                             ignore_start_enrollment=False):
    """Checks whether a person can enroll for an activity

    :param request: The request object of the current request, needed to put it in django messages
    :param activity: The activity for which we need to check whether the person can enroll for it
    :param person: The person who wants to enroll for an activity, standard is request.person
    :param indirect: Whether the enrollment is done by the person him-/herself, or done for him/her
    :param ignore_full: Ignore the enrollment limit of the activity
    :param ignore_start_enrollment: Ignore the enrollment period of the activity
    :returns: Whether the person can enroll for the given activity

    :side_effect: Puts an elaborate description of the error in django messages
    """

    if not person:
        person = request.person
        indirect = False

    if not person.is_member():
        messages.error(request,
                       _('Enrollment for {activity} is not possible. You do not have an active membership at Inter-Actief').format(
                           activity=activity,
                       ))

        # shorted because we only want to return an error
        return False

    if not activity.enrollment:
        messages.error(request,
                       _('Unenrollment for {activity} is not possible.').format(
                           activity=activity,
                       ))
        return False

    if activity.oauth_application:
        messages.error(request,
                       _('Enrollment for {activity} is only possible on the website of this activity.').format(
                           activity=activity,
                       ))
        return False

    if not activity.enrollment_open():
        if not ignore_start_enrollment:
            messages.error(request,
                           _("The enrollment period for {activity} hasn't started yet or has already passed.").format(
                               activity=activity,
                           ))
            return False

    if person in activity.participants.all():
        if indirect:
            messages.error(request,
                           _('{person} is already enrolled for {activity}.').format(
                               person=person,
                               activity=activity,
                           ))
        else:
            messages.error(request,
                           _('You are already enrolled for {activity}.').format(
                               activity=activity,
                           ))
        return False

    return True


def check_unenrollment_allowed(request, activity, person=None, indirect=False, ignore_can_unenroll=False,
                               ignore_unenrollment_period=False):
    """Checks whether a person can unenroll for an activity

    :param request: The request object of the current request, needed to put it in django messages
    :param activity: The activity for which we need to check whether the person can unenroll
    :param person: The person who wants to unenroll for an activity, standard is request.person
    :param indirect: Whether the unenrollment is done by the person him-/herself or for him/her
    :param ignore_can_unenroll: Ignore the unenrollment prohibition of the activity
    :param ignore_unenrollment_period: Ignore the unenrollment period of the activity
    :returns: Whether the person can unenroll for the given activity

    :side_effect: Puts an elaborate description of the error in django messages
    """

    if not person:
        person = request.person
        indirect = False

    if not activity.enrollment:
        messages.error(request,
                       _('Unenrollment for {activity} is not possible.').format(
                           activity=activity,
                       ))
        return False

    if activity.oauth_application:
        messages.error(request,
                       _('Unenrollment for {activity} is only possible on the website of this activity.')
                       .format(
                           activity=activity,
                       ))
        return False

    try:
        # The select_for_update makes sure to acquire a write lock
        Participation.objects.select_for_update().get(person=person, event=activity)
    except Participation.DoesNotExist:
        if indirect:
            messages.error(request,
                           _('{person} is not enrolled for {activity}.').format(
                               person=person,
                               activity=activity,
                           ))
        else:
            messages.error(request,
                           _('You are not enrolled for {activity}.').format(
                               activity=activity,
                           ))
        return False

    if not (ignore_can_unenroll or activity.can_unenroll):
        messages.error(request,
                       _('Unenrollment for {activity} is not possible.').format(
                           activity=activity,
                       ))
        return False

    if not (ignore_unenrollment_period or activity.enrollment_open()):
        messages.error(request,
                       _('The unenrollment term for {activity} has already passed.').format(
                           activity=activity,
                       ))
        return False

    return True


@transaction.atomic
def update_waiting_list(activity=None, request=None, **kwargs):
    if activity is None:
        activity = kwargs.get('instance')

    while not activity.enrollment_full() and activity.has_waiting_participants() and not activity.waiting_list_locked:
        new_participation = Participation.objects.get(
            person=activity.waiting_participants.order_by('participation__added_on').first(),
            event=activity)

        activity_send_enrollmentmail(new_participation, from_waiting_list=True)
        new_participation.waiting_list = False
        new_participation.save()
        from amelie.personal_tab import transactions
        transactions.add_participation(new_participation)
        if request is not None and request.is_board:
            messages.info(request, _(u'{person} has been promoted from the waiting list for {activity}.').format(
                person=new_participation.person, activity=activity))



LOCALE_LOCK = threading.Lock()


@contextmanager
def setlocale(name):
    """
    A Contextmanager to change the locale within the context to the given locale string.
    This allows tools like strptime to parse time strings in other locales than the system locale.
    e.g. "with setlocale('en_US'): ..."
    """
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)

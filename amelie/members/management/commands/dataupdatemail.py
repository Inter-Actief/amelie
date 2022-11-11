from django.core.management.base import BaseCommand

from amelie.iamailer.mailtask import MailTask
from amelie.members.models import Person, Preference
from amelie.tools.mail import PersonRecipient


def dataupdate_context(person):
    study = None
    if hasattr(person, 'student'):
        study_periods = person.student.studyperiod_set.filter(end__isnull=True)
        study = ', '.join([x.study.name for x in study_periods])

    preferences = {}
    for preference in Preference.objects.filter(adjustable=True):
        # Translation of preferences here because the .preference property takes the
        # language of the person sending the mail, not the person that it needs to go to.
        if person.preferred_language == 'nl':
            preferences[preference.preference_nl] = preference in person.preferences.all()
        else:
            preferences[preference.preference_en] = preference in person.preferences.all()

    context = {"person": person, "study": study, "preferences": preferences}
    return context


class Command(BaseCommand):
    args = ''
    help = ''

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument(
            '--confirm',
            action='store_true',
            dest='confirm',
            default=False,
            help='Confirm sending the data mail to ALL members'
        )

    def handle(self, *args, **options):

        if options['confirm']:
            members = Person.objects.members().all()

            from_contact = "Board of Inter-Actief <board@inter-actief.net>"
            task = MailTask(from_=from_contact, template_name='members/data_mail.mail', report_to=from_contact)

            self.stdout.write("Building messages...")

            for person in members:
                context = dataupdate_context(person)

                task.add_recipient(PersonRecipient(recipient=person,
                                                   context=context))

            self.stdout.write("Sending messages...")

            task.send(delay=False)

        else:
            print("This command sends a message to ALL members to check their data.\n"
                  "If you are sure about this, add --confirm to the command.")

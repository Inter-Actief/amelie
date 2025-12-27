from datetime import date

from django.core.management.base import BaseCommand

from amelie.iamailer import MailTask
from amelie.tools.const import TaskPriority
from amelie.members.models import Person
from amelie.tools.mail import PersonRecipient


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        birthdays = Person.objects.members().filter(date_of_birth__day=date.today().day,
                                                    date_of_birth__month=date.today().month).distinct()

        for person in birthdays:
            if hasattr(person, 'student') and person.has_preference(name='mail_birthday'):
                task = MailTask(from_="Board of Inter-Actief <board@inter-actief.net>",
                                template_name='birthday_mail.mail',
                                report_to="Board of Inter-Actief <board@inter-actief.net>",
                                report_always=False,
                                priority=TaskPriority.MEDIUM)

                task.add_recipient(PersonRecipient(person, context={'age': person.age()}))

                # Send email
                task.send(delay=False)

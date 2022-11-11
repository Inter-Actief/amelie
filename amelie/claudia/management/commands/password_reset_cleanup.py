from django.core.management.base import BaseCommand
from django.utils import timezone

from amelie.members.models import Person


class Command(BaseCommand):
    help = 'Clean-up all expired password reset codes. Supposed to be ran as a cronjob every hour.'

    def handle(self, *args, **options):
        people = Person.objects.filter(password_reset_code__isnull=False, password_reset_expiry__lt=timezone.now())

        self.stdout.write('Deleting expired password reset codes...')

        for person in people:
            self.stdout.write("- Removing code for {}".format(person.incomplete_name()))
            person.password_reset_code = None
            person.password_reset_expiry = None
            person.save()

        self.stdout.write('Password reset code cleanup complete!')

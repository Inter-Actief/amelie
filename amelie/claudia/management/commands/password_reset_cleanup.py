from django.core.management.base import BaseCommand
from django.utils import timezone

from amelie.members.models import Person


class Command(BaseCommand):
    help = 'Clean-up all expired password reset codes. Supposed to be ran as a cronjob every hour.'

    def handle(self, *args, **options):

        self.stdout.write('Deleting expired password reset codes...')

        people_pass = Person.objects.filter(password_reset_code__isnull=False, password_reset_expiry__lt=timezone.now())
        for person in people_pass:
            self.stdout.write("- Removing password code for {}".format(person.incomplete_name()))
            person.password_reset_code = None
            person.password_reset_expiry = None
            person.save()


        self.stdout.write('Deleting expired sudo password reset codes...')

        people_sudo = Person.objects.filter(sudo_reset_code__isnull=False, sudo_reset_expiry__lt=timezone.now())
        for person in people_sudo:
            self.stdout.write("- Removing sudo code for {}".format(person.incomplete_name()))
            person.sudo_reset_code = None
            person.sudo_reset_expiry = None
            person.save()

        self.stdout.write('Password reset code cleanup complete!')

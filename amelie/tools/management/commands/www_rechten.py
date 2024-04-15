from django.core.management.base import CommandError

from amelie.members.models import Committee, Person, Membership
from amelie.tools.management.base import DevelopmentOnlyCommand


class Command(DevelopmentOnlyCommand):
    help = 'Give all committee members of the WWW committee staff- and superuser powers.'

    changes_database = True

    def handle(self, *args, **options):
        # Check for OK
        if not super(Command, self).handle(*args, **options):
            return

        # Get WWW committee
        try:
            www_committee = Committee.objects.get(abbreviation="WWW", abolished__isnull=True)
        except Committee.DoesNotExist:
            raise CommandError('WWW-committee not found, does it exist?')

        # Make everyone a superuser
        for www_function in www_committee.function_set.filter(end__isnull=True):
            user = www_function.person.user
            user.is_staff = True
            user.is_superuser = True
            user.save()

            self.stdout.write("%s is now a superuser\n" % www_function.person)

        # Add Beun as a member
        Person.objects.create(first_name="Beun", last_name_prefix="de", last_name="Beunhaas",
                              initials="B.", notes="WWW Testuser", gender="Other", international_member="Yes",
                              address="a", postal_code="b", city="c", account_name="beun")

        # Done
        self.stdout.write("Done!\n")

from django.core.management.base import BaseCommand

from amelie.members.models import Person, Study
from amelie.tools.logic import current_association_year


class Command(BaseCommand):
    help = 'Remove the data of parents for all members that are not in their first year of membership'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help='Save changes'
        )

    def handle(self, *args, **options):
        commit = options['commit']
        if not commit:
            self.stderr.write('** TESTMODE **')
            self.stderr.write('Add --commit to save changes')

        self.stdout.write("This command will remove all parents data from members that are not in their first year of bachelor in {}.".format(current_association_year()))

        self.stdout.write("Generating list of persons that need to be checked...")

        # People who are now in their first year of bachelor
        first_years = [
            x for x in Person.objects.all()
            if hasattr(x, 'student') and len([
                y for y in list(x.student.studyperiod_set.all())
                if y.begin.year == current_association_year() and y.study.type == Study.StudyTypes.BSC
            ]) != 0
        ]

        # All members
        all_members = Person.objects.all()

        # Target group; second years and higher
        targets = all_members.exclude(id__in=[x.id for x in first_years])

        self.stdout.write("Removing parent data...")

        for x in targets:
            lid = x.membership_set.exclude(year=current_association_year())

            if lid.count() > 0:
                changed = False
                changes = []

                if x.address_parents != "":
                    if commit:
                        x.address_parents = ""
                    changed = True
                    changes.append("address")

                if x.postal_code_parents != "":
                    if commit:
                        x.postal_code_parents = ""
                    changed = True
                    changes.append("postal_code")

                if x.city_parents != "":
                    if commit:
                        x.city_parents = ""
                    changed = True
                    changes.append("city")

                if x.country_parents != "":
                    if commit:
                        x.country_parents = ""
                    changed = True
                    changes.append("country")

                if x.email_address_parents != "":
                    if commit:
                        x.email_address_parents = ""
                    changed = True
                    changes.append("email")

                if changed and commit:
                    x.save()

                if changed:
                    self.stdout.write("{}: {}".format(x, changes))

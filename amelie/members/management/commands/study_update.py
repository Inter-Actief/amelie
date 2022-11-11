import datetime

from django.core.management.base import BaseCommand, CommandError

from amelie.members.models import Study, StudyPeriod, Person, Student


class Command(BaseCommand):
    help = 'Update study information from members based on lists from BOZ'
    args = 'study_abbreviation:filename ...'

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

        today = datetime.date.today()

        studies = {}

        for arg in args:
            study_abbreviation, filename = arg.split(':', 1)
            try:
                study = Study.objects.get(abbreviation=study_abbreviation)
            except Study.DoesNotExist:
                raise CommandError(u"Study {} not found.".format(study_abbreviation))

            # Read student number from the file
            numbers = set()
            try:
                with open(filename) as f:
                    for line in f:
                        if line.strip():
                            numbers.add(int(line.strip()))
            except IOError as e:
                raise CommandError(u"Reading file {} failed: {}".format(filename, e))

            studies[study] = numbers

        # List of student numbers with master enrollment
        master_numbers = set()
        for study, numbers in studies.items():
            if study.type == Study.StudyTypes.MSC:
                master_numbers.update(numbers)

        members = Person.objects.members()

        for study, numbers in studies.items():
            self.stdout.write(str(study))

            # Study periods to end
            sps_to_end = StudyPeriod.objects.filter(study=study, end__isnull=True, student__person__in=members)\
                .exclude(student__number__in=numbers)

            for sp in sps_to_end:
                # Assume that the bachelor is successfully completed if there is a master enrollment.
                sp.graduated = (study.type == Study.StudyTypes.BSC and sp.student.number in master_numbers) or study.type == Study.StudyTypes.MSC
                sp.end = today

                if commit:
                    sp.save()

                self.stdout.write('Ended: {} (graduated {})'.format(sp, sp.graduated))

            # New student periods that need to be added
            numbers_new = numbers - set(study.studyperiod_set.values_list('student__number', flat=True))
            students_new = Student.objects.filter(number__in=numbers_new, person__in=members)

            for student in students_new:
                sp = StudyPeriod(student=student, study=study, begin=today)

                if commit:
                    sp.save()

                self.stdout.write('New: {}'.format(sp))

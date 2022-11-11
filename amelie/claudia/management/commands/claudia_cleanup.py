import datetime
from optparse import make_option

from django.core.management.base import BaseCommand
from django.utils import timezone

from amelie.claudia.models import Mapping, ExtraPerson, ExtraGroup, Timeline


class Command(BaseCommand):
    args = 'claudia_cleanup'
    help = "Clean up old Claudia mappings, extra objects and timelines"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Save changes'
        )

    def handle(self, *args, **options):
        force = options['force']

        if not force:
            self.stdout.write('** TESTMODE **')
            self.stdout.write('Add --force to delete objects')
            self.stdout.write('')

        # About 15 months
        deadline = timezone.now() - datetime.timedelta(days=15*30)

        self.stdout.write('')
        self.stdout.write('** Unused mappings')
        # Inactive mappings without an account (guid) with no timeline in the last 15 months
        mappings = Mapping.objects.filter(active=False, guid='').exclude(timeline__datetime__gte=deadline)

        for mp in mappings:
            self.stdout.write('Mapping %s (#%d)' % (mp, mp.pk))
            if force:
                # Directly delete all related timelines
                mp.timeline_set.all().delete()
                mp.delete()

        self.stdout.write('')
        self.stdout.write('** Unused extra persons')
        if not force:
            self.stdout.write('* Additional extra persons can be unused after deleting mappings *')

        # Inactive extra persons ...
        extra_persons = ExtraPerson.objects.filter(active=False)
        for extra_person in extra_persons:
            if not Mapping.find(extra_person):
                # ... without a mapping
                self.stdout.write('Extra person %s (#%d)' % (extra_person, extra_person.pk))
                if force:
                    extra_person.delete()

        self.stdout.write('')
        self.stdout.write('** Unused extra groups')
        if not force:
            self.stdout.write('* Additional extra groups can be unused after deleting mappings *')

        # Inactive extra groups ...
        extra_groups = ExtraGroup.objects.filter(active=False)
        for extra_group in extra_groups:
            if not Mapping.find(extra_group):
                # ... without a mapping
                self.stdout.write('Extra group %s (#%d)' % (extra_group, extra_group.pk))
                if force:
                    extra_group.delete()

        self.stdout.write('')
        self.stdout.write('** Old unowned timelines')

        # Timelines not linked to a mapping older than 15 months
        timelines = Timeline.objects.filter(datetime__lte=deadline, mapping__isnull=True)
        self.stdout.write('%d unowned timelines' % len(timelines))
        if force:
            timelines.delete()

        if not force:
            self.stdout.write('')
            self.stdout.write('** TESTMODE **')
            self.stdout.write('Add --force to delete objects')

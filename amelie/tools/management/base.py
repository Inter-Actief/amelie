from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class DevelopmentOnlyCommand(BaseCommand):
    # Settings are required
    can_import_settings = True

    def add_arguments(self, parser):
        super(DevelopmentOnlyCommand, self).add_arguments(parser=parser)

        # Add the --ok option
        parser.add_argument(
            '--ok',
            action='store_true',
            dest='ok',
            default=False,
            help='Actually execute the action.'
        )

    def handle(self, *args, **options):
        # Check for production/development
        if not getattr(settings, 'DEBUG', False):
            raise CommandError('This command can only be run under DEBUG=True mode! '
                               'You are possibly running this on a production server!')

        if getattr(self, 'changes_database', False):
            self.stdout.write("WARNING: This command will modify the database!\n")

        if not options['ok']:
            self.stdout.write("To actually execute this function, please pass in the option '--ok'.\n")
            return False

        return True

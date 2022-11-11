from django.core.management.base import BaseCommand

from amelie.data_export.models import DataExport

class Command(BaseCommand):
    help = 'Clean-up all expired data exports made by members. Supposed to be ran as a cronjob every hour.'

    def handle(self, *args, **options):
        exports = DataExport.objects.all()

        self.stdout.write('Deleting expired data exports...')

        for export in exports:
            if export.is_expired:
                self.stdout.write('- Export {} deleted.'.format(export.id))
                export.delete()

        self.stdout.write('Data export cleanup complete!')

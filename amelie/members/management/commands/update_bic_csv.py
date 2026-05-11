from django.core.management.base import BaseCommand, CommandError

import requests
import os

from django.conf import settings

class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Updating BIC list, downloading BIC CSV'))

        response = requests.get("https://www.europeanpaymentscouncil.eu/sites/default/files/participants_export/sdd_core/sdd_core.csv",
                                headers={
                                    'Accept': 'text/csv; charset=utf-8'
                                })
        try:
            csv_file = open(os.path.join(settings.MEDIA_ROOT, 'data/bic_list.csv'), "w+")
            csv_file.write(response.content.decode("utf8"))
            csv_file.close()
            self.stdout.write(self.style.SUCCESS('BIC list successfully updated'))
        except IOError as e:
            raise CommandError(u"Creating file {} failed: {}".format(os.path.join(settings.MEDIA_ROOT, 'bic_list.csv'), e))

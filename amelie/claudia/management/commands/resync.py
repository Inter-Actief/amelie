from django.core.management.base import BaseCommand

from amelie.claudia.clau import Claudia


class Command(BaseCommand):
    help = 'Resync all Claudia data'

    def handle(self, *args, **options):
        Claudia().check_integrity()

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from amelie.claudia.ad import AD
from amelie.claudia.models import Event


class Command(BaseCommand):
    args = 'delete_users'
    help = "Delete expired AD user accounts"

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
            self.stdout.write('Add --force to delete the accounts')
            self.stdout.write('')

        events = Event.objects.filter(type='DELETE_USER', execute__lte=timezone.now())
        mps = [event.mapping for event in events]

        a = settings.CLAUDIA_AD
        ad = AD(a["LDAP"], a["HOST"], a["USER"], a["PASSWORD"], a["BASEDN"], a["PORT"], a["CACERTFILE"])

        for mp in mps:
            if mp.get_guid():
                account = ad.get_person_guid(mp.get_guid())
                if account:
                    self.stdout.write(mp.adname)

                    if force:
                        account.delete()
                        mp.set_guid(account.guid())
                        mp.save()
                else:
                    self.stderr.write("Account %s for %s not found" % (mp.adname, mp.name))

        if force:
            for event in events:
                event.delete()

        if not force:
            self.stdout.write('')
            self.stdout.write('** TESTMODE **')
            self.stdout.write('Add --force to delete the accounts')

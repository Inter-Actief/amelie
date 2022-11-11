import csv
import random

from auditlog.models import LogEntry
from django.contrib.sessions.models import Session
from fcm_django.models import FCMDevice
from django.contrib.auth.models import User
from social_django.models import UserSocialAuth, Association, Code, Nonce, Partial
from django.utils import timezone

from amelie.claudia.models import Timeline
from amelie.members.models import Committee, Person, UnverifiedEnrollment, Membership, MembershipType
from amelie.personal_tab.models import Authorization, DebtCollectionInstruction
from amelie.tools.management.base import DevelopmentOnlyCommand


class Command(DevelopmentOnlyCommand):
    help = 'Obfuscate all personal details of members to be used in development purposes.'

    changes_database = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument(
            '--file',
            dest='file',
            help='CSV-file with random names'
        )

    def handle(self, *args, **options):
        # Check for OK
        if not super(Command, self).handle(*args, **options):
            return

        # Check for csv-file
        if not options['file']:
            self.stderr.write("You have to give a csv-file with random names with the option --file <file>.")
            return

        # Print warning
        self.stdout.write('This command might take a while (10-15 min).\n')

        # Read CSV file
        csv_file = open(options['file'], 'r')
        csv_data = csv.reader(csv_file, delimiter=',', quotechar='"')
        rows = [row for row in csv_data]
        csv_file.close()

        # Randomize data
        random.shuffle(rows)
        pointer = 0

        www_members = Person.objects.filter(function__committee=Committee.objects.get(abbreviation="WWW"),
                                            function__end__isnull=True)

        for person in Person.objects.exclude(pk__in=www_members):
            pointer = self.obfuscate_person(person, pointer, rows)

        for pre_enrollment in UnverifiedEnrollment.objects.all():
            pointer = self.obfuscate_person(pre_enrollment, pointer, rows)

        # Create a User, Person and Membership object with no special rights and
        # link it to the "beun" account for testing by www'ers.
        beun_user, created = User.objects.get_or_create(username='beun')
        if created:
            beun = Person.objects.create(
                first_name='Beun', last_name_prefix='de', last_name='Beunhaas', initials='B.',
                slug='beun', gender='Unknown', address='Hallenweg 11', postal_code='7522 NH',
                city='Enschede', country='Nederland', email_address='www@inter-actief.net',
                telephone='0534893756', account_name='beun', user=beun_user
            )
            Membership.objects.bulk_create([
                Membership(member=beun, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                           year=timezone.now().year - 1),
                Membership(member=beun, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                           year=timezone.now().year),
                Membership(member=beun, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                           year=timezone.now().year + 1),
            ])

        # Delete authorizations
        for authorization in Authorization.objects.exclude(person__in=www_members):
            if authorization.person:
                # Get person name for account holder name field
                authorization.account_holder_name = authorization.person.incomplete_name()
                authorization.iban = "NL13TEST0123456789"
                authorization.bic = "TESTNL2A"

                authorization.save()

        # Delete direct debit descriptions
        for instruction in DebtCollectionInstruction.objects.all():
            instruction.description = "Direct Debit Instruction #{}".format(instruction.pk)
            instruction.save()

        # Delete device data
        FCMDevice.objects.all().delete()

        # Delete sessions
        Session.objects.all().delete()

        # Delete audits
        LogEntry.objects.all().delete()

        # Delete all oauth authorizations
        Association.objects.all().delete()
        Code.objects.all().delete()
        Nonce.objects.all().delete()
        Partial.objects.all().delete()
        UserSocialAuth.objects.all().delete()

        # Delete Claudia Timeline
        Timeline.objects.all().delete()

        # Done
        self.stdout.write("Done!\n")

    def obfuscate_person(self, person, pointer, rows):
        person.first_name = rows[pointer][0]
        person.last_name_prefix = ""
        person.last_name = rows[pointer][1]
        person.initials = rows[pointer][2]
        person.address = "Hallenweg 11"
        person.postal_code = "7522 NB"
        person.city = "Enschede"
        person.country = "Nederland"
        person.address_parents = "Hallenweg 11"
        person.postal_code_parents = "7522 NB"
        person.city_parents = "Enschede"
        person.country_parents = "Nederland"
        person.telephone = "0600000000"
        person.email_address = "www@inter-actief.utwente.nl"
        # Obfuscate gender, 25% will be man, 25% will be woman, 25% will be unknown, 25% will be other
        person.gender = random.choice(Person.GenderTypes.values)
        # Obfuscate internationality, 33% will be dutch, 33% will be international, 33% will be unknown
        person.international_member = random.choice(Person.InternationalChoices.values)
        pointer = (pointer + 1) % len(rows)
        person.save()
        return pointer

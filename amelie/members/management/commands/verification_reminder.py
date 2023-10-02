from django.core.management.base import BaseCommand, CommandError

from amelie.iamailer.mailtask import MailTask
from amelie.members.models import Membership, MembershipType
from amelie.tools.mail import PersonRecipient


class Command(BaseCommand):
    help = "Send membership verification reminder to unverified memberships."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument('from_year')
        parser.add_argument('to_year')
        parser.add_argument(
            '--send',
            action='store_true',
            dest='send',
            default=False,
            help='Actually send the e-mails'
        )

    def handle(self, *args, **options):
        send_mails = options['send']
        if not send_mails:
            self.stderr.write('** TEST MODE **')
            self.stderr.write('Add --send to save changes')

        try:
            current_year = int(options['from_year'])
            new_year = int(options['to_year'])
        except ValueError:
            raise CommandError("Type numbers for years...")

        studylongmembershiptypes_text = [
            'Studielang (eerste jaar)',
            'Studielang (vervolg)',
        ]
        studylongmembershiptypes = MembershipType.objects.filter(name_nl__in=studylongmembershiptypes_text)

        unverified_memberships = Membership.objects.filter(year=current_year,
                                                           type__in=studylongmembershiptypes,
                                                           type__needs_verification=True,
                                                           verified_on__isnull=True,
                                                           ended__isnull=True
                                                           )
        total_memberships = len(unverified_memberships)
        self.stdout.write(f"{total_memberships} active unverified memberships that still need verification")

        reminder_mails = MailTask(from_='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                  template_name='members/verification_reminder.mail',
                                  report_to='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                  report_language='nl',
                                  report_always=True)

        for i, membership in enumerate(unverified_memberships):
            # Check if there actually is a new membership already,
            # do not send a reminder mail in those cases.
            already_exists = False
            try:
                new_membership = Membership.objects.get(member=membership.member, year=new_year, ended__isnull=True)
            except Membership.DoesNotExist:
                pass
            else:
                already_exists = True

            if already_exists:
                self.stdout.write(f"[{i}/{total_memberships}] {membership.member.incomplete_name()}:\n"
                                  f"  - New membership already exists ({new_membership}), skipping.")
            else:
                reminder_mails.add_recipient(PersonRecipient(recipient=membership.member))
                self.stdout.write(f"[{i}/{total_memberships}] {membership.member.incomplete_name()}: Added")

        self.stdout.write(u"Sending mails...")

        if send_mails:
            reminder_mails.send()
        else:
            self.stdout.write("...but not really... (option --send not given).")

        self.stdout.write(u"Done")

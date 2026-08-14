from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from amelie.iamailer import MailTask
from amelie.personal_tab.transactions import get_personal_tab_balances
from amelie.tools.const import TaskPriority
from amelie.tools.mail import PersonRecipient


class Command(BaseCommand):
    help = "Send open balance reminder to members that have a positive open personal tab balance but no authorization."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
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

        self.stdout.write(self.style.SUCCESS(f'Calculating personal tab balances...'))

        balances_per_person = get_personal_tab_balances(only_members=True, only_without_mandate=True)
        task = MailTask(from_="I.C.T.S.V. Inter-Actief <treasurer@inter-actief.net>",
                        template_name='personal_tab/balance_reminder.mail',
                        report_to="I.C.T.S.V. Inter-Actief <treasurer@inter-actief.net>",
                        report_always=False,
                        priority=TaskPriority.MEDIUM)

        # Filter balances list to only positive, above minimum amount.
        num_recipients = 0
        for bal in balances_per_person:
            if bal['person'].pk != 3289:
                continue
            if bal['balance'] <= settings.PERSONAL_TAB_MINIMUM_BALANCE_REMINDER:
                continue  # Balance too low for reminder
            task.add_recipient(PersonRecipient(bal['person'], context={
                'balance': bal['balance'],
                'num_unpaid_transactions': bal['unpaid_transactions'].count(),
                'overview_link': urljoin(settings.ABSOLUTE_PATH_TO_SITE, reverse('personal_tab:person_transactions_unpaid', kwargs={
                    'pk': bal['person'].pk, 'slug': bal['person'].slug
                })),
            }))
            num_recipients += 1

        if num_recipients > 0:
            self.stdout.write(self.style.SUCCESS(f'Sending balance reminder emails to {num_recipients} members...'))
            if send_mails:
                task.send()
            else:
                self.stdout.write("...but not really... (option --send not given).")
        else:
            self.stdout.write(self.style.SUCCESS(f'No recipients, not sending e-mails...'))
        self.stdout.write("Done")

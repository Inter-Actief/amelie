from django.core.management.base import BaseCommand

from amelie.iamailer.mailtask import MailTask, Recipient


class Command(BaseCommand):
    args = 'test_mail <recipient ...>'
    help = "Test iamailer"

    def handle(self, *args, **options):
        task = MailTask(from_=args[0], template_name='iamailer/testmail.mail')

        for arg in args:
            recipient = Recipient([arg], ccs=[args[0]])
            task.add_recipient(recipient)

        self.stdout.write('Sending mail to {} recipients...'.format(len(args)))

        task.send(delay=False)

        self.stdout.write('Mail sent.')

from datetime import date
from datetime import timedelta

from django.core.management.base import BaseCommand

from amelie.companies.models import Company, WebsiteBanner
from amelie.iamailer import MailTask, Recipient


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        banners = WebsiteBanner.objects.filter(
            end_date__gte=date.today(), end_date__lte=date.today()+timedelta(weeks=4)).distinct()
        companies = Company.objects.filter(end_date__gte=date.today(), end_date__lte=date.today() + timedelta(weeks=4))\
            .distinct()

        task = MailTask(from_="External Helper <www@inter-actief.net>",
                        template_name='companies/bannercheck.mail',
                        report_to="External Helper <www@inter-actief.net>",
                        report_always=False)

        context = {
            'companies': companies,
            'banners': banners
        }

        task.add_recipient(Recipient(
            tos=['samenwerking@inter-actief.net'],
            context=context
            ))

        # Send E-mail
        task.send(delay=False)

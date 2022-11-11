from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone
from social_django.models import Partial

from amelie.oauth.models import LoginToken


class Command(BaseCommand):
    EXPIRE_PARTIAL_AFTER = timedelta(hours=24)

    help = 'Delete login tokens and partial pipelines that are older than 24 hours'

    def handle(self, *args, **options):
        deadline_token = timezone.now() - LoginToken.EXPIRE_AFTER
        LoginToken.objects.filter(date__lt=deadline_token).delete()

        deadline_partial = timezone.now() - Command.EXPIRE_PARTIAL_AFTER
        Partial.objects.filter(timestamp__lt=deadline_partial).delete()
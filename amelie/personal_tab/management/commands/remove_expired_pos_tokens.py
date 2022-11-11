from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from amelie.personal_tab.pos_models import PendingPosToken


class Command(BaseCommand):
    help = "Removes POS (Point of Sale) login/card registration tokens that have expired and can not be used any more." \
           "Supposed to be ran as a cronjob every 5 minutes."

    def handle(self, *args, **options):
        # The POS QR code shows for 2 minutes, and it might take a few seconds more to verify the token.
        # So, to allow for some slack, but not to allow tokens to exist too long,
        # tokens should be valid for about 3 minutes. This command might run less often than that, but that's fine.
        expiry_datetime = timezone.now() - timedelta(minutes=3)

        # All tokens with a creation date earlier then the expiry date should be removed.
        tokens = PendingPosToken.objects.filter(created_at__lt=expiry_datetime)
        num_tokens = tokens.count()
        if num_tokens > 0:
            tokens.delete()
            self.stdout.write("{} expired Personal Tab POS tokens removed.".format(num_tokens))

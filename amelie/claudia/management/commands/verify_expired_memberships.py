import datetime

from django.core.management import BaseCommand

from amelie.claudia.tools import verify_instance
from amelie.members.models import Membership


class Command(BaseCommand):
    help = 'Verify all members within the past week with an expired membership'

    def handle(self, *args, **options):
        today = datetime.datetime.today()
        week_ago = today - datetime.timedelta(days=7)
        expired_memberships = Membership.objects.filter(ended__gte=week_ago, ended__lte=today)

        for membership in expired_memberships:
            person = membership.member
            verify_instance(instance=person)

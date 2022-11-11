import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from amelie.members.models import Person
from amelie.personal_tab.alexia import get_alexia, parse_datetime
from amelie.personal_tab.models import AlexiaTransaction


class Command(BaseCommand):
    help = "Import transactions from Alexia"

    def handle(self, *args, **options):

        server = get_alexia()

        orders = server.order.unsynchronized()

        for order in orders:
            transaction_id = int(order['id'])

            with transaction.atomic():
                if AlexiaTransaction.objects.select_for_update().filter(transaction_id=transaction_id).exists():
                    self.stderr.write("Transaction %i already imported" % transaction_id)
                    continue

                username = order['authorization']['user']

                if re.match(r'^s[0-9]{7}', username):
                    try:
                        student_number = int(username[1:])
                        person = Person.objects.get(student__number=student_number)
                    except Person.DoesNotExist:
                        self.stderr.write("Username not found: %s" % username)
                        continue
                elif re.match(r'^m[0-9]{7}', username):
                    try:
                        employee_number = int(username[1:])
                        person = Person.objects.get(employee__number=employee_number)
                    except Person.DoesNotExist:
                        self.stderr.write("Username not found: %s" % username)
                        continue
                else:
                    self.stderr.write("Invalid username format: %s" % username)
                    continue

                date = parse_datetime(order['placed_at'])
                price = sum([Decimal(p['price']) for p in order['purchases']])
                description = order['event']['name']

                alexia_transaction = AlexiaTransaction(date=date, price=price, person=person, description=description,
                                                       transaction_id=transaction_id)
                alexia_transaction.save()

            server.order.marksynchronized(transaction_id)

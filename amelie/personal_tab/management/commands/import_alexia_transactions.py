import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from amelie.members.models import Person
from amelie.personal_tab.alexia import get_alexia, parse_datetime
from amelie.personal_tab.models import AlexiaTransaction, RFIDCard


class Command(BaseCommand):
    help = "Import transactions from Alexia"

    def handle(self, *args, **options):
        self.stdout.write(f"Importing unsynchronized transactions from Alexia...")

        server = get_alexia()

        self.stdout.write(f"Retrieving unsynchronized transactions from Alexia...")
        orders = server.order.unsynchronized()
        num_orders = len(orders)
        self.stdout.write(f"{num_orders} unsynchronized orders to process...")

        for i, order in enumerate(orders):
            transaction_id = int(order['id'])
            self.stdout.write(f"[{i+1}/{num_orders}] Processing order #{transaction_id}...")

            with transaction.atomic():
                if AlexiaTransaction.objects.select_for_update().filter(transaction_id=transaction_id).exists():
                    self.stderr.write(f"[{i+1}/{num_orders}] Transaction #{transaction_id} already imported")
                    continue

                username = order['authorization']['user']

                if re.match(r'^s[0-9]{7}', username):
                    try:
                        student_number = int(username[1:])
                        person = Person.objects.get(student__number=student_number)
                    except Person.DoesNotExist:
                        self.stderr.write(f"[{i+1}/{num_orders}] Username not found: {username}")
                        continue
                elif re.match(r'^m[0-9]{7}', username):
                    try:
                        employee_number = int(username[1:])
                        person = Person.objects.get(employee__number=employee_number)
                    except Person.DoesNotExist:
                        self.stderr.write(f"[{i+1}/{num_orders}] Username not found: {username}")
                        continue
                else:
                    self.stderr.write(f"[{i+1}/{num_orders}] Invalid username format: {username}")
                    continue

                self.stdout.write(f"[{i+1}/{num_orders}] Identified order user as {person}...")

                date = parse_datetime(order['placed_at'])
                price = sum([Decimal(p['price']) for p in order['purchases']])
                description = order['event']['name']

                # Try to update the last used time on the RFID card that was used for the transaction
                try:
                    rfid_card = person.rfid_card.get(code=order['rfid'])
                    rfid_card.last_used = timezone.now()
                    rfid_card.save()
                    self.stdout.write(f"[{i+1}/{num_orders}] Last used date updated for RFID card '{rfid_card}' of {person}.")
                except RFIDCard.DoesNotExist:
                    self.stdout.write(f"[{i+1}/{num_orders}] Could not update last used date for RFID card. RFID card not found with code '{order['rfid']}', user '{username}', person {person}.")

                alexia_transaction = AlexiaTransaction(date=date, price=price, person=person, description=description,
                                                       transaction_id=transaction_id)
                alexia_transaction.save()
                self.stdout.write(f"[{i+1}/{num_orders}] Alexia transaction #'{alexia_transaction.pk}' of {person} created.")

            self.stdout.write(f"[{i+1}/{num_orders}] Marking transaction #'{alexia_transaction.pk}' as synchronized in Alexia...")
            server.order.marksynchronized(transaction_id)

        self.stdout.write(f"Alexia transaction import completed.")

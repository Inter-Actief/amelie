import uuid

import os

from django.core.management.base import BaseCommand

from amelie.members.models import Person
from django.conf import settings


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        files = os.listdir(os.path.join(settings.MEDIA_ROOT, 'pasfoto'))

        for f in files:
            student_number_string = f[1:8]
            if student_number_string.isdigit():
                student_number_int = int(student_number_string)
                try:
                    p = Person.objects.get(student__number=student_number_int)
                    if not p.picture:
                        full_new_path = os.path.join(settings.MEDIA_ROOT, "pasfoto", "{}.{}".format(uuid.uuid4(), f.split('.')[-1]))
                        os.rename(os.path.join(settings.MEDIA_ROOT, "pasfoto", f), full_new_path)
                        p.picture = 'pasfoto/{}'.format(os.path.basename(full_new_path))
                        p.save()
                except Person.DoesNotExist:
                    print("Student for file {} does not exist".format(f))
                except Person.MultipleObjectsReturned:
                    print("help {}".format(f))

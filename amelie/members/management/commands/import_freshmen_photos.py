import uuid

import os

from django.core.management.base import BaseCommand

from amelie.members.models import Person
from django.conf import settings


class Command(BaseCommand):
    args = 'Import freshmen pictures named after student numbers from a local directory into Amelie.'
    help = 'import_directory'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument('import_directory')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help='Save changes'
        )

    def handle(self, *args, **options):
        import_directory = options['import_directory']
        commit = options['commit']
        if not commit:
            self.stderr.write('** TEST MODE **')
            self.stderr.write('Add --commit to save changes')

        import_files = os.listdir(import_directory)

        for f in import_files:
            if f[0] == "s":
                student_number_string = f[1:8]
            else:
                student_number_string = f[0:7]

            if student_number_string.isdigit():
                student_number_int = int(student_number_string)
                try:
                    p = Person.objects.get(student__number=student_number_int)
                    if not p.picture:
                        new_filename = "{}.{}".format(uuid.uuid4(), f.split('.')[-1])
                        full_new_path = os.path.join(settings.MEDIA_ROOT, "profile_picture", new_filename)
                        if not commit:
                            os.rename(os.path.join(import_directory, f), full_new_path)
                            p.picture = 'profile_picture/{}'.format(os.path.basename(full_new_path))
                            p.save()
                        print(f"{f} -> {new_filename} ({p})")
                    else:
                        print(f"Person {p} already has a picture, skipping file {f}.")
                except Person.DoesNotExist:
                    print(f"Student for file {f} does not exist")
                except Person.MultipleObjectsReturned:
                    print(f"Multiple persons found for file {f}. help")
            else:
                print(f"File {f} is not named after a student number in format '[0-9]+' or 's[0-9]+'.")

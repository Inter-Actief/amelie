from django.core.management.base import BaseCommand

from amelie.files.models import Attachment


class Command(BaseCommand):
    help = "Update all the dimensions of photos in the database"

    def handle(self, *args, **options):
        self.stdout.write("All photos are provided with new dimensions. This can take a while!\n")

        for photo in Attachment.objects.all():
            photo.save(create_thumbnails=False)

        self.stdout.write("Done!\n")

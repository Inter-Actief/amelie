from io import StringIO
from django.test import TestCase

from django.core.management import call_command


class MissingMigrationTest(TestCase):
    def testMissingMigrations(self):
        output = StringIO()
        try:
            call_command(
                'makemigrations', interactive=False, dry_run=True, check=True,
                stdout=output)
        except SystemExit as e:
            # The exit code will be non-zero when model changes without migrations are detected.
            if str(e) != '0':
                self.fail("There are missing migrations:\n %s" % output.getvalue())

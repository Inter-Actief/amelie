import json
import datetime
import random
from typing import Dict

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.education.models import EducationEvent
from amelie.files.models import Attachment
from amelie.members.models import Committee
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests


def generate_education_events():
    """
    Generate Education Events for testing.

    It will generate 4 events:
    - A public event that is visible
    - A public event that is not visible
    - A private event that is visible
    - A private event that is not visible
    """

    now = timezone.now()
    committee = Committee.objects.all()[0]

    i = 0
    for public in [True, False]:
        i += 1
        start = now + datetime.timedelta(days=i, seconds=random.uniform(0, 5*3600))
        end = start + datetime.timedelta(seconds=random.uniform(3600, 10*3600))

        event = EducationEvent(
            begin=start, end=end, summary_nl='Test Event %i' % i,
            summary_en='Test event %i' % i,
            organizer=committee, public=public,
            education_organizer="Education organizer"
        )
        event.save()


class EducationGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Education app
    """

    def setUp(self):
        super(EducationGraphQLPrivateFieldTests, self).setUp()

        # Generate education events
        generate_education_events()

        # Retrieve those events
        self.public_event = EducationEvent.objects.filter(public=True).order_by('-id').first()
        self.private_event = EducationEvent.objects.filter(public=False).order_by('-id').first()

        # Add a private and public attachment to the public visible event
        self.public_attachment = Attachment(
            public=True, file=SimpleUploadedFile("public.txt", b"File Contents")
        )
        self.public_attachment.save(create_thumbnails=False)
        self.private_attachment = Attachment(
            public=False, file=SimpleUploadedFile("private.txt", b"Secret Contents")
        )
        self.private_attachment.save(create_thumbnails=False)

        self.public_event.attachments.add(self.public_attachment)
        self.public_event.attachments.add(self.private_attachment)


    EDUCATION_EVENT_PRIVATE_FIELDS: Dict[str, str] = {
        "callback_url": "callbackUrl",
        "callback_secret_key": "callbackSecretKey",
        "update_count": "updateCount",

        # organizer private subfields
        "organizer.abbreviation": "organizer { abbreviation }",
        "organizer.private_email": "organizer { privateEmail }",
        "organizer.superuser": "organizer { superuser }",
        "organizer.gitlab": "organizer { gitlab }",
        "organizer.ledger_account_number": "organizer { ledgerAccountNumber }",

        # organizer.function_set private subfields
        "organizer.function_set.note": "organizer { functionSet { note }}",
    }

    def test_education_event_private_model(self):
        # Test if private events cannot be retrieved
        self._test_private_model(
            query_name="educationEvent",
            variables={"id": (self.private_event.id, "ID")}
        )

    def test_education_events_private_model(self):
        # Test if private events cannot be retrieved via list view
        self._test_private_model_list(
            query_name="educationEvents",
            public_field_spec="results { id }",
            variables={"id": (self.private_event.id, "ID")}
        )

    def test_education_event_private_fields(self):
        # Test if private fields on public events cannot be retrieved
        for field_name, field_spec in self.EDUCATION_EVENT_PRIVATE_FIELDS.items():
            self._test_public_model_and_private_field(
                query_name="educationEvent", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_event.id, "ID")},
            )

    def test_education_events_private_fields(self):
        # Test if private fields on public events cannot be retrieved via list view
        for field_name, field_spec in self.EDUCATION_EVENT_PRIVATE_FIELDS.items():
            # Wrap the field spec in "results { <SPEC> }" for list view
            field_spec = f"results {{ {field_spec} }}"
            self._test_public_model_and_private_field(
                query_name="educationEvents", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_event.id, "ID")}
            )

    def test_education_event_private_attachment(self):
        # Test if private event attachments are hidden in get view
        query = "query ($id: ID) { educationEvent(id: $id) { attachments { public }}}"
        response = self.query(query, variables={"id": self.public_event.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'educationEvent', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['educationEvent']['attachments']),
                        f"Query for 'educationEvent', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['educationEvent']['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'educationEvent', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_education_events_private_attachment(self):
        # Test if private event attachments are hidden in list view
        query = "query ($id: ID) { educationEvents(id: $id) { results { attachments { public }}}}"
        response = self.query(query, variables={"id": self.public_event.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'educationEvents', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['educationEvents']['results'][0]['attachments']),
                        f"Query for 'educationEvents', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['educationEvents']['results'][0]['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'educationEvents', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

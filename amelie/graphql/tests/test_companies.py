import json
import datetime
import random
from typing import Dict

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.companies.models import Company, CompanyEvent, WebsiteBanner, VivatBanner, TelevisionBanner
from amelie.files.models import Attachment
from amelie.members.models import Committee
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests


def generate_company_events():
    """
    Generate Company Events for testing.

    It will generate 4 events:
    - A public event that is visible
    - A public event that is not visible
    - A private event that is visible
    - A private event that is not visible
    """

    now = timezone.now()
    committee = Committee.objects.all()[0]
    start = now - datetime.timedelta(days=10)
    end = start + datetime.timedelta(days=20)
    company = Company.objects.create(
        name_nl="Bedrijf", name_en="Company", url="https://inter-actief.net",
        profile_nl="Een bedrijf", profile_en="A company", start_date=start, end_date=end
    )

    i = 0
    for public in [True, False]:
        for visible in [True, False]:
            i += 1
            start = now + datetime.timedelta(days=i, seconds=random.uniform(0, 5*3600))
            end = start + datetime.timedelta(seconds=random.uniform(3600, 10*3600))

            if visible:
                visible_from = now - datetime.timedelta(days=5)
                visible_till = now + datetime.timedelta(days=5)
            else:
                visible_from = now - datetime.timedelta(days=15)
                visible_till = now - datetime.timedelta(days=5)

            event = CompanyEvent(
                begin=start, end=end, summary_nl='Test Event %i' % i,
                summary_en='Test event %i' % i,
                organizer=committee, public=public, company=company,
                visible_from=visible_from, visible_till=visible_till
            )
            event.save()


class CompaniesGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Companies app
    """

    def setUp(self):
        super(CompaniesGraphQLPrivateFieldTests, self).setUp()

        # Generate company events
        generate_company_events()

        # Retrieve those events
        now = timezone.now()
        self.public_visible_event = CompanyEvent.objects.filter(public=True, visible_from__lt=now, visible_till__gt=now).order_by('-id').first()
        self.public_invisible_event = CompanyEvent.objects.filter(public=True, visible_till__lt=now).order_by('-id').first()
        self.private_visible_event = CompanyEvent.objects.filter(public=False, visible_from__lt=now, visible_till__gt=now).order_by('-id').first()
        self.private_invisible_event = CompanyEvent.objects.filter(public=False, visible_till__lt=now).order_by('-id').first()

        # Add a private and public attachment to the public visible event
        self.public_attachment = Attachment(
            public=True, file=SimpleUploadedFile("public.txt", b"File Contents")
        )
        self.public_attachment.save(create_thumbnails=False)
        self.private_attachment = Attachment(
            public=False, file=SimpleUploadedFile("private.txt", b"Secret Contents")
        )
        self.private_attachment.save(create_thumbnails=False)

        self.public_visible_event.attachments.add(self.public_attachment)
        self.public_visible_event.attachments.add(self.private_attachment)


    COMPANY_EVENT_PRIVATE_FIELDS: Dict[str, str] = {
        "visible_from": "visibleFrom",
        "visible_till": "visibleTill",
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

    def test_company_event_private_model(self):
        # Test if public, but invisible, and private events cannot be retrieved
        self._test_private_model(
            query_name="companyEvent",
            variables={"id": (self.public_invisible_event.id, "ID")}
        )
        self._test_private_model(
            query_name="companyEvent",
            variables={"id": (self.private_visible_event.id, "ID")}
        )
        self._test_private_model(
            query_name="companyEvent",
            variables={"id": (self.private_invisible_event.id, "ID")}
        )

    def test_company_events_private_model(self):
        # Test if public, but invisible, and private events cannot be retrieved via list view
        self._test_private_model_list(
            query_name="companyEvents",
            public_field_spec="results { id }",
            variables={"id": (self.public_invisible_event.id, "ID")}
        )
        self._test_private_model_list(
            query_name="companyEvents",
            public_field_spec="results { id }",
            variables={"id": (self.private_visible_event.id, "ID")}
        )
        self._test_private_model_list(
            query_name="companyEvents",
            public_field_spec="results { id }",
            variables={"id": (self.private_invisible_event.id, "ID")}
        )

    def test_company_event_private_fields(self):
        # Test if private fields on public events cannot be retrieved
        for field_name, field_spec in self.COMPANY_EVENT_PRIVATE_FIELDS.items():
            self._test_public_model_and_private_field(
                query_name="companyEvent", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_visible_event.id, "ID")},
            )

    def test_company_events_private_fields(self):
        # Test if private fields on public events cannot be retrieved via list view
        for field_name, field_spec in self.COMPANY_EVENT_PRIVATE_FIELDS.items():
            # Wrap the field spec in "results { <SPEC> }" for list view
            field_spec = f"results {{ {field_spec} }}"
            self._test_public_model_and_private_field(
                query_name="companyEvents", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_visible_event.id, "ID")}
            )

    def test_company_event_private_attachment(self):
        # Test if private event attachments are hidden in get view
        query = "query ($id: ID) { companyEvent(id: $id) { attachments { public }}}"
        response = self.query(query, variables={"id": self.public_visible_event.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'companyEvent', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['companyEvent']['attachments']),
                        f"Query for 'companyEvent', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['companyEvent']['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'companyEvent', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_company_events_private_attachment(self):
        # Test if private event attachments are hidden in list view
        query = "query ($id: ID) { companyEvents(id: $id) { results { attachments { public }}}}"
        response = self.query(query, variables={"id": self.public_visible_event.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'companyEvents', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['companyEvents']['results'][0]['attachments']),
                        f"Query for 'companyEvents', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['companyEvents']['results'][0]['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'companyEvents', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

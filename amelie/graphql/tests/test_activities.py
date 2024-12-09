import json
from typing import Dict

from django.core.files.uploadedfile import SimpleUploadedFile

from amelie.activities.models import Activity
from amelie.files.models import Attachment
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests
from amelie.tools.tests import generate_activities


class ActivitiesGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Activities app
    """

    def setUp(self):
        super(ActivitiesGraphQLPrivateFieldTests, self).setUp()

        # Generate two activities, one public and one private
        generate_activities(2)

        # Retrieve those activities
        self.public_activity = Activity.objects.filter(public=True).order_by('-id').first()
        self.private_activity = Activity.objects.filter(public=False).order_by('-id').first()

        # Add a private and public photo and attachment to the public activity
        self.public_attachment = Attachment(
            public=True, file=SimpleUploadedFile("public.txt", b"File Contents")
        )
        self.public_attachment.save(create_thumbnails=False)
        self.private_attachment = Attachment(
            public=False, file=SimpleUploadedFile("private.txt", b"Secret Contents")
        )
        self.private_attachment.save(create_thumbnails=False)
        self.public_activity.attachments.add(self.public_attachment)
        self.public_activity.attachments.add(self.private_attachment)
        self.public_activity.photos.add(self.public_attachment)
        self.public_activity.photos.add(self.private_attachment)


    ACTIVITY_PRIVATE_FIELDS: Dict[str, str] = {
        "facebook_event_id": "facebookEventId",
        "oauth_application": "oauthApplication",
        "participants": "participants",
        "callback_url": "callbackUrl",
        "callback_secret_key": "callbackSecretKey",
        "update_count": "updateCount",

        # Reverse foreign keys (Event)
        "participation": "participation",

        # organizer private subfields
        "organizer.abbreviation": "organizer { abbreviation }",
        "organizer.private_email": "organizer { privateEmail }",
        "organizer.superuser": "organizer { superuser }",
        "organizer.gitlab": "organizer { gitlab }",
        "organizer.ledger_account_number": "organizer { ledgerAccountNumber }",

        # organizer.function_set private subfields
        "organizer.function_set.note": "organizer { functionSet { note }}",
    }

    def test_activity_private_model(self):
        # Test if private activity cannot be retrieved
        self._test_private_model(
            query_name="activity",
            variables={"id": (self.private_activity.id, "ID")}
        )

    def test_activities_private_model(self):
        # Test if private activity cannot be retrieved via list view
        self._test_private_model_list(
            query_name="activities",
            public_field_spec="results { id }",
            variables={"id": (self.private_activity.id, "ID")}
        )

    def test_activity_private_fields(self):
        # Test if private fields on public activities cannot be retrieved
        for field_name, field_spec in self.ACTIVITY_PRIVATE_FIELDS.items():
            self._test_public_model_and_private_field(
                query_name="activity", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_activity.id, "ID")},
            )

    def test_activities_private_fields(self):
        # Test if private fields on public activities cannot be retrieved via list view
        for field_name, field_spec in self.ACTIVITY_PRIVATE_FIELDS.items():
            # Wrap the field spec in "results { <SPEC> }" for list view
            field_spec = f"results {{ {field_spec} }}"
            self._test_public_model_and_private_field(
                query_name="activity", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.public_activity.id, "ID")}
            )

    def test_activity_private_attachment(self):
        # Test if private activity attachments are hidden in get view
        query = "query ($id: ID) { activity(id: $id) { attachments { public }}}"
        response = self.query(query, variables={"id": self.public_activity.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'activity', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['activity']['attachments']),
                        f"Query for 'activity', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['activity']['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'activity', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_activities_private_attachment(self):
        # Test if private activity attachments are hidden in list view
        query = "query ($id: ID) { activities(id: $id) { results { attachments { public }}}}"
        response = self.query(query, variables={"id": self.public_activity.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'activities', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['activities']['results'][0]['attachments']),
                        f"Query for 'activities', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['activities']['results'][0]['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'activities', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_activity_private_photo(self):
        # Test if private activity photos are hidden in get view
        query = "query ($id: ID) { activity(id: $id) { photos { public }}}"
        response = self.query(query, variables={"id": self.public_activity.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'activity', public field 'photos' returned an error!"
        )

        # Check that all photos are public, and that the correct amount of photos are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['activity']['photos']),
                        f"Query for 'activity', public field 'photos' returned a private photo!")
        num_photos = len(content['data']['activity']['photos'])
        self.assertEqual(
            num_photos, 1,
            f"Query for 'activity', public field 'photos' did not return 1 expected photo (returned {num_photos})!"
        )

    def test_activities_private_photo(self):
        # Test if private activity photos are hidden in list view
        query = "query ($id: ID) { activities(id: $id) { results { photos { public }}}}"
        response = self.query(query, variables={"id": self.public_activity.id})
        content = json.loads(response.content)

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'activities', public field 'photos' returned an error!"
        )

        # Check that all photos are public, and that the correct amount of photos are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['activities']['results'][0]['photos']),
                        f"Query for 'activity', public field 'photos' returned a private photo!")
        num_photos = len(content['data']['activities']['results'][0]['photos'])
        self.assertEqual(
            num_photos, 1,
            f"Query for 'activities', public field 'photos' did not return 1 expected photo (returned {num_photos})!"
        )

from django.core.files.uploadedfile import SimpleUploadedFile

from amelie.files.models import Attachment
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests


class FilesGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Files app
    """

    def setUp(self):
        super(FilesGraphQLPrivateFieldTests, self).setUp()

        # Create a private attachment
        self.private_attachment = Attachment(
            public=False, file=SimpleUploadedFile("private.txt", b"Secret Contents")
        )
        self.private_attachment.save(create_thumbnails=False)


    def test_attachment_private_model(self):
        # Test if private attachment cannot be retrieved
        self._test_private_model(
            query_name="attachment",
            public_field_spec="public",
            variables={"id": (self.private_attachment.id, "ID")}
        )

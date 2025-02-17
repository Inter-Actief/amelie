from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.graphql.tests import BaseGraphQLPrivateFieldTests
from amelie.publications.models import Publication, PublicationType


def generate_publication() -> Publication:
    """
    Generate Publication for testing.

    It will generate 1 private publication
    """

    now = timezone.now()

    # Create PublicationType
    publication_type = PublicationType(
        type_name="Publication Type",
        description="This is a publication type.",
        default_thumbnail=SimpleUploadedFile("thumb.png", b"Some PNG")
    )
    publication_type.save()
    # Create publication
    item = Publication(
        name=f"Publication",
        description="This is a publication",
        date_published=now,
        publication_type=publication_type,
        file=SimpleUploadedFile("publication.txt", b"This is a very nice publication"),
        public=False
    )
    item.save()
    return item


class PublicationsGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Publications app
    """

    def setUp(self):
        super(PublicationsGraphQLPrivateFieldTests, self).setUp()

        # Generate two publications, one public and one private
        self.private_publication = generate_publication()

    def test_publication_private_model(self):
        # Test if private publication cannot be retrieved
        self._test_private_model(
            query_name="publication",
            variables={"id": (self.private_publication.id, "ID")}
        )

    def test_publications_private_model(self):
        # Test if private publication cannot be retrieved via list view
        self._test_private_model_list(
            query_name="publications",
            public_field_spec="results { id }",
            variables={"id": (self.private_publication.id, "ID")}
        )

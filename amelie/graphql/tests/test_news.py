import json

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.news.models import NewsItem
from amelie.files.models import Attachment
from amelie.members.models import Committee, Person
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests
from amelie.tools.tests import generate_activities


def generate_news_article() -> NewsItem:
    """
    Generate News article for testing.

    It will generate 1 article with:
    - a public attachment
    - a private attachment
    - a linked public activity
    - a linked private activity
    """

    now = timezone.now()
    committee = Committee.objects.first()
    author = Person.objects.first()

    # Generate two activities, one public and one private
    generate_activities(2)

    item = NewsItem(
        publication_date=now,
        title_nl=f"Nieuwsartikel",
        title_en=f"News Article",
        introduction_nl="Dit is een nieuwsartikel.",
        introduction_en="This is a news article.",
        content_nl="Dit is de inhoud.",
        content_en="This is the content.",
        publisher=committee,
        author=author,
    )
    item.save()

    # Add public attachment
    public_attachment = Attachment(
        public=True, file=SimpleUploadedFile("public.txt", b"File Contents")
    )
    public_attachment.save(create_thumbnails=False)
    item.attachments.add(public_attachment)

    # Add private attachment
    private_attachment = Attachment(
        public=False, file=SimpleUploadedFile("public.txt", b"File Contents")
    )
    private_attachment.save(create_thumbnails=False)
    item.attachments.add(private_attachment)

    # Add linked public activity
    public_activity = Activity.objects.filter(public=True).order_by('-id').first()
    item.activities.add(public_activity)

    # Add linked private activity
    private_activity = Activity.objects.filter(public=False).order_by('-id').first()
    item.activities.add(private_activity)

    return item

class NewsGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the News app
    """

    def setUp(self):
        super(NewsGraphQLPrivateFieldTests, self).setUp()

        # A committee with the abbreviation of the education committee is required for the news module
        # functions to work properly. So we get_or_create it here to make sure it exists in the test DB.
        _ = Committee.objects.get_or_create(name="EduCom", abbreviation=settings.EDUCATION_COMMITTEE_ABBR)

        # Generate news article
        self.article = generate_news_article()

    def test_news_item_private_attachment(self):
        # Test if private attachments are hidden in get view
        query = "query ($id: ID) { newsItem(id: $id) { attachments { public }}}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItem', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['newsItem']['attachments']),
                        f"Query for 'newsItem', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['newsItem']['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'newsItem', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_news_items_private_attachment(self):
        # Test if private attachments are hidden in list view
        query = "query ($id: ID) { newsItems(id: $id) { results { attachments { public }}}}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItems', public field 'attachments' returned an error!"
        )

        # Check that all attachments are public, and that the correct amount of attachments are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['newsItems']['results'][0]['attachments']),
                        f"Query for 'newsItems', public field 'attachments' returned a private attachment!")
        num_attachments = len(content['data']['newsItems']['results'][0]['attachments'])
        self.assertEqual(
            num_attachments, 1,
            f"Query for 'newsItems', public field 'attachments' did not return 1 expected attachment (returned {num_attachments})!"
        )

    def test_news_item_private_activity(self):
        # Test if private activities are hidden in get view
        query = "query ($id: ID) { newsItem(id: $id) { activities { public }}}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItem', public field 'activities' returned an error!"
        )

        # Check that all activities are public, and that the correct amount of activities are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['newsItem']['activities']),
                        f"Query for 'newsItem', public field 'activities' returned a private attachment!")
        num_activities = len(content['data']['newsItem']['activities'])
        self.assertEqual(
            num_activities, 1,
            f"Query for 'newsItem', public field 'activities' did not return 1 expected attachment (returned {num_activities})!"
        )

    def test_news_items_private_activity(self):
        # Test if private activities are hidden in list view
        query = "query ($id: ID) { newsItems(id: $id) { results { activities { public }}}}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItems', public field 'activities' returned an error!"
        )

        # Check that all activities are public, and that the correct amount of activities are received (1)
        self.assertTrue(all(a['public'] == True for a in content['data']['newsItems']['results'][0]['activities']),
                        f"Query for 'newsItems', public field 'activities' returned a private attachment!")
        num_activities = len(content['data']['newsItems']['results'][0]['activities'])
        self.assertEqual(
            num_activities, 1,
            f"Query for 'newsItems', public field 'activities' did not return 1 expected activity (returned {num_activities})!"
        )

    def test_news_item_author_publisher_string(self):
        # Test if the author and publisher of a news item are a strings in get view
        query = "query ($id: ID) { newsItem(id: $id) { author, publisher }}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItem', public fields 'author, publisher' returned an error!"
        )

        # Check that both author and publisher fields are strings
        self.assertTrue(isinstance(content['data']['newsItem']['author'], str),
                        f"Query for 'newsItem', public field 'author' returned something else than a string!")
        self.assertTrue(isinstance(content['data']['newsItem']['publisher'], str),
                        f"Query for 'newsItem', public field 'author' returned something else than a string!")

    def test_news_items_author_publisher_string(self):
        # Test if the author and publisher of a news item are a strings in list view
        query = "query ($id: ID) { newsItems(id: $id) { results { author, publisher }}}"
        response = self.query(query, variables={"id": self.article.id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'newsItems', public fields 'author, publisher' returned an error!"
        )

        # Check that both author and publisher fields are strings
        self.assertTrue(isinstance(content['data']['newsItems']['results'][0]['author'], str),
                        f"Query for 'newsItem', public field 'author' returned something else than a string!")
        self.assertTrue(isinstance(content['data']['newsItems']['results'][0]['publisher'], str),
                        f"Query for 'newsItem', public field 'author' returned something else than a string!")

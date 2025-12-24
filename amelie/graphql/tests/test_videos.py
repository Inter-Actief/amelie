import json
from typing import Tuple

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.news.models import NewsItem
from amelie.files.models import Attachment
from amelie.members.models import Committee, Person
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests
from amelie.videos.models import BaseVideo, YouTubeVideo, StreamingIAVideo, PeertubeIAVideo
from amelie.tools.tests import generate_activities


def generate_videos():
    """
    Generate Video for testing.

    It will generate 4 videos
    - A public YouTube video
    - A public Streaming.IA video
    - A private YouTube video
    - A private Streaming.IA video
    """

    now = timezone.now()
    committee = Committee.objects.first()

    for i in range(2):
        # Create video
        item = YouTubeVideo(
            video_id=i,
            title=f"YouTube Video {i + 1}",
            description="This is a Youtube video.",
            date_published=now,
            publisher=committee,
            public=bool(i)
        )
        item.save()
        item = StreamingIAVideo(
            video_id=i,
            title=f"Streaming.IA Video {i + 1}",
            description="This is a Streaming.IA video.",
            date_published=now,
            publisher=committee,
            public=bool(i)
        )
        item.save()
        item = PeertubeIAVideo(
            video_id=i,
            title=f"Video.IA Video {i + 1}",
            description="This is a Video.IA video.",
            date_published=now,
            publisher=committee,
            public=bool(i)
        )
        item.save()


class VideosGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Videos app
    """

    def setUp(self):
        super(VideosGraphQLPrivateFieldTests, self).setUp()

        # Generate four videos, public and private, YouTube and Streaming.IA videos.
        generate_videos()

        # Retrieve and store those videos
        self.public_yt_video = YouTubeVideo.objects.filter(public=True).order_by('-video_id').first()
        self.private_yt_video = YouTubeVideo.objects.filter(public=False).order_by('-video_id').first()
        self.public_ia_video = StreamingIAVideo.objects.filter(public=True).order_by('-video_id').first()
        self.private_ia_video = StreamingIAVideo.objects.filter(public=False).order_by('-video_id').first()

    def test_video_private_model(self):
        # Test if private videos cannot be retrieved
        self._test_private_model(
            query_name="video",
            public_field_spec="videoId",
            variables={"videoId": (self.private_yt_video.video_id, "ID")}
        )
        self._test_private_model(
            query_name="video",
            public_field_spec="videoId",
            variables={"videoId": (self.private_ia_video.video_id, "ID")}
        )

    def test_videos_private_model(self):
        # Test if private videos cannot be retrieved via list view
        self._test_private_model_list(
            query_name="videos",
            public_field_spec="results { videoId }",
            variables={"videoId": (self.private_yt_video.video_id, "ID")}
        )
        self._test_private_model_list(
            query_name="videos",
            public_field_spec="results { videoId }",
            variables={"videoId": (self.private_ia_video.video_id, "ID")}
        )

    def test_video_publisher_string(self):
        # Test if the publisher of a video is a string in get view
        query = "query ($videoId: ID) { video(videoId: $videoId) { publisher }}"
        response = self.query(query, variables={"videoId": self.public_yt_video.video_id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'video', public field 'publisher' returned an error!"
        )

        # Check that both author and publisher fields are strings
        self.assertTrue(isinstance(content['data']['video']['publisher'], str),
                        f"Query for 'video', public field 'publisher' returned something else than a string!")

    def test_videos_publisher_string(self):
        # Test if the publisher of a video is a string in list view
        query = "query ($videoId: ID) { videos(videoId: $videoId) { results { publisher }}}"
        response = self.query(query, variables={"videoId": self.public_yt_video.video_id})
        content = response.json()

        # The request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for 'videos', public field 'publisher' returned an error!"
        )

        # Check that both author and publisher fields are strings
        self.assertTrue(isinstance(content['data']['videos']['results'][0]['publisher'], str),
                        f"Query for 'newsItem', public field 'publisher' returned something else than a string!")


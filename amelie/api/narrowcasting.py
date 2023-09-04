import datetime
from typing import List, Dict

import random

from django.conf import settings
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.api.activitystream_utils import add_images_property, add_thumbnails_property
from amelie.api.decorators import authentication_optional
from amelie.api.utils import parse_datetime_parameter
from amelie.companies.models import TelevisionBanner, CompanyEvent
from amelie.education.models import EducationEvent
from amelie.news.models import NewsItem
from amelie.narrowcasting.models import TelevisionPromotion
from amelie.room_duty.models import RoomDuty
from amelie.tools.templatetags import md

from modernrpc.core import rpc_method


@rpc_method(name='getBanners')
def get_narrowcasting_banners() -> List[Dict]:
    """
    Retrieves a list of active sponsored narrowcasting banners.

    **Module**: `narrowcasting`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the banners.

      Each returned element in the list has the following fields:

        - id: The identifier for this banner
        - name: The title of this banner
        - image: An URL to the image of a banner

    **Example:**

        --> {"method":"getBanners", "params":[]}
        <-- {"result": [{
               "id": 15,
               "name": "Super awesome company, work here!",
               "image": "https://url.to/banner.png"
        }]}
    """
    result = []
    banners = TelevisionBanner.objects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now(), active=True)

    for banner in banners:
        result.append({
            "name": banner.name,
            "image": "%s%s" % (settings.MEDIA_URL, str(banner.picture)),
            "id": banner.id
        })

    return result


@rpc_method(name='getNews')
def get_news(amount: int, render_markdown: bool = False) -> List[Dict]:
    """
    Retrieves a list of recent news articles.

    **Module**: `narrowcasting`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - amount: The ID of the requested news item.
        - render_markdown: A boolean that indicates if the introduction and content should be rendered to HTML.
                           Optional, default false (content will be returned as markdown).

    **Return:**
      `List[Dict]`: An array of dictionaries containing the news articles.

      Each returned element in the list has the following fields:

        - id: The id of this news item
        - title: The title of this news item
        - url: The url of this news item
        - publicationDate: The publication date of this news item. (RFC3339)
        - introduction: A short introduction to this news item
        - content: The content of this news item

    **Example:**

        --> {"method":"getNews", "params":[1]}
        <-- {"result": [{
               "id": 490,
               "title": "The new Symposium Committee!",
               "publicationDate": "2022-05-25T17:00:00+00:00",
               "introduction": "Today the new Symposium Committee has been formed!",
               "content": "markdown _contents_ excluding introduction"
               "url": "/news/490/2022/05/25/the-new-symposium-committee/"
        }]}

        --> {"method":"getNews", "params":[1, true]}
        <-- {"result": [{
               "id": 490,
               "title": "The new Symposium Committee!",
               "publicationDate": "2022-05-25T17:00:00+00:00",
               "introduction": "<p>Today the new Symposium Committee has been formed!</p>",
               "content": "<p><!-- html contents excluding introduction --></p>",
               "url": "/news/490/2022/05/25/the-new-symposium-committee/"
        }]}
    """
    result = []
    news_articles = NewsItem.objects.all()[0:amount]

    for news in news_articles:
        result.append({
            "id": news.id,
            "title": news.title,
            "publicationDate": news.publication_date,
            "introduction": md.markdown(news.introduction) if render_markdown else news.introduction,
            "content": md.markdown(news.content) if render_markdown else news.content,
            "url": news.get_absolute_url(),
        })

    return result


@rpc_method(name='getTelevisionPromotions')
def get_television_promotions() -> List[Dict]:
    """
    Retrieves a list of promoted events.

    **Module**: `narrowcasting`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the banners.

      Each returned element in the list has the following fields:

        - title: The title of the event
        - image: An URL to the image of an event
        - signup: True if it is possible to sign up for this activity, optional (only if signup is available)
        - signupStart: The start date of the signup period (RFC3339), optional (only if signup is available)
        - signupStop: The signup deadline (RFC3339), optional (only if signup is available)
        - signupMaximum: Maximum allowed attendees, optional (only if signup is available)
        - signupAvailable: Amount of current attendees, optional (only if signup is available)

    **Example:**

        --> {"method":"getTelevisionPromotions", "params":[]}
        <-- {"result": [{
               "title": "Water Skiing!",
               "image": "https://url.to/promotion.png",
               "signup": true,
               "signupStart":"2022-07-03T18:00:00+00:00",
               "signupStop":"2022-07-08T18:00:00+00:00",
               "signupMaximum":40,
               "signupAvailable":12
        }]}
    """
    result = []
    promotions = TelevisionPromotion.objects.filter(start__lte=timezone.now(), end__gte=timezone.now())

    for promotion in promotions:
        res_dict = {
            "image": "%s%s" % (settings.MEDIA_URL, str(promotion.attachment))
        }

        if promotion.activity:
            res_dict["title"] = promotion.activity.description
            if promotion.activity.enrollment:
                res_dict["signup"] = promotion.activity.enrollment
                res_dict["signupStart"] = promotion.activity.enrollment_begin.isoformat()
                res_dict["signupStop"] = promotion.activity.enrollment_end.isoformat()
                res_dict["signupMaximum"] = promotion.activity.maximum
                res_dict["signupAvailable"] = promotion.activity.places_available()

        result.append(res_dict)

    return result


@rpc_method(name='getPhotos')
@authentication_optional()
def get_activity_photos(days: int, photos_per_activity: int, **kwargs) -> List[str]:
    """
    Retrieves an amount of photos from recent activities.
    If a person is authenticated, non-public pictures will also be included.

    **Module**: `narrowcasting`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - days: How many days ago an activity can be to still be included.
        - photos_per_activity: The (maximum) amount of pictures per activity to return.

    **Return:**
      `List[str]`: An array of URLs to the photos.

    **Example:**

        --> {"method":"getPhotos", "params":[60, 2]}
        <-- {"result": [
               "https://url.to/photo1-1.png",
               "https://url.to/photo1-2.png",
               "https://url.to/photo2-1.png",
               "https://url.to/photo2-2.png"
            ]}
    """
    authenticated = kwargs.get('authentication', None) is not None
    result = []

    activities = Activity.objects.filter_public(not authenticated)\
        .filter(begin__gte=(timezone.now() - datetime.timedelta(days=days)))

    for activity in activities:
        candidates = []

        for photo in activity.photos.all():
            if photo.public:
                candidates.append(photo.file.url)

        if len(candidates) > photos_per_activity:
            result += random.sample(candidates, photos_per_activity)
        else:
            result += candidates

    return result


@rpc_method(name='getHistoricActivitiesWithPictures')
@authentication_optional()
def get_historic_activity_with_pictures(begin_date_str: str, end_date_str: str, amount: int, **kwargs) -> List[Dict]:
    """
    Retrieves a list of a number of random activities between two dates that have pictures.
    If a person is authenticated, non-public pictures will also be included.

    **Module**: `narrowcasting`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - begin_date_str: The start date from which to consider activities. (RFC3339, inclusive)
        - end_date_str: The end date until which to consider activities. (RFC3339, exclusive)
        - amount: The (maximum) amount of activities to return.

    **Return:**
      `List[Dict]`: An array of dictionaries containing the activities.

      Each returned element in the list has the following fields:

        - id: The ID for this activity
        - title: The title of this activity
        - location: The location of this event.
        - beginDate: The starting date and time of this event (RFC3339)
        - endDate: The end date and time of this event (RFC3339)
        - source: The source of this event (always "inter-actief")
        - url: The URL to the pictures page of this event.
        - category: The type of this activity (either "regular", "educational" or "external")
        - isDutch: A boolean value indicating if the activity is Dutch-only
        - organizer: The organizer of this activity
        - thumbnails: A dictionary with the following fields:
          - small: URL to a small size version of the thumbnail (max. 256x256), if available, else null.
          - medium: URL to a medium size version of the thumbnail (max. 800x600), if available, else null.
          - large: URL to a large size version of the thumbnail (max. 1600x1200), if available, else null.
          - original: The URL to the original thumbnail.
        - images: List of dictionaries of the images for this activity. Each dictionary contains the following fields:
          - small: URL to a small size version of the picture (max. 256x256), if available, else null.
          - medium: URL to a medium size version of the picture (max. 800x600), if available, else null.
          - large: URL to a large size version of the picture (max. 1600x1200), if available, else null.
          - original: The URL to the original picture.

    **Example:**

        --> {"method":"getHistoricActivitiesWithPictures",
             "params":["2022-07-01T00:00:00+02:00", "2022-07-31T23:59:59+02:00", 1]}
        <-- {"result": [{
               "id": 1337
               "title": "Awesome Activity!",
               "location": "SmartXP",
               "beginDate": "2022-07-01T18:56:50+00:00",
               "endDate": "2022-07-01T20:56:50+00:00",
               "source": "inter-actief",
               "url": "/activities/1337/photos/",
               "category": "regular",
               "isDutch": false
               "organizer": "Board",
               "thumbnail": {
                 "small": "https://url.to/small/image.png",
                 "medium": "https://url.to/medium/image.png",
                 "large": "https://url.to/large/image.png",
                 "original": "https://url.to/original/image.png"
               },
               "images": [
                 {
                   "small": "https://url.to/small/image.png",
                   "medium": "https://url.to/medium/image.png",
                   "large": "https://url.to/large/image.png",
                   "original": "https://url.to/original/image.png",
                 }, {...}, {...}, ...
               ]
        }]}
    """
    authenticated = kwargs.get('authentication', None) is not None
    begin_date = parse_datetime_parameter(begin_date_str)
    end_date = parse_datetime_parameter(end_date_str)

    activities = Activity.objects.filter_public(not authenticated).filter(photos__gt=0,
                                                                          begin__gt=begin_date,
                                                                          begin__lt=end_date).distinct()

    if not authenticated:
        activities = activities.filter(photos__public=True)

    # Shuffle the activities so random ones are at the start
    activities = list(activities)
    random.shuffle(activities)
    activities = activities[0:amount]

    result = []
    for activity in activities:
        single = {
            "id": activity.id,
            "title": activity.summary,
            "location": activity.location,
            "beginDate": activity.begin.isoformat(),
            "endDate": activity.end.isoformat(),
            "source": "inter-actief",
            "category": activity.activity_type,
            "url": activity.get_photo_url(),
            "isDutch": activity.dutch_activity,
        }

        if type(activity) == EducationEvent:
            single["organizer"] = activity.education_organizer
        elif type(activity) == CompanyEvent:
            single["organizer"] = activity.company.name if activity.company else activity.company_text
        else:
            single["organizer"] = activity.organizer.name

        add_thumbnails_property(activity, kwargs.get('authentication', None), single)
        add_images_property(activity, kwargs.get('authentication', None), single)

        result.append(single)

    return result


@rpc_method(name='getRoomDutyToday')
@authentication_optional()
def get_room_duty_today(**kwargs) -> List[Dict]:
    """
    Retrieve the room duty schedule for today.

    **Module**: `narrowcasting`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing the details for each room duty shift for today.

      Each returned element in the list has the following fields:

        - beginDate: The starting date and time of this room duty shift (RFC3339)
        - endDate: The end date and time of this room duty shift (RFC3339)
        - participants: List of dictionaries with the names of people who have room duty in this shift.
                        Each dictionary contains the following fields:
          - firstName: First name of someone who has room duty.
          - lastName: Last name of someone who has room duty.
          - fullName: Full name of someone who has room duty.

    **Example:**

        --> {"method":"getRoomDutyToday", "params":[]}
        <-- {"result": [{
               "beginDate": "2023-01-09T08:00:00+00:00",
               "endDate": "2023-01-09T11:30:00+00:00",
               "participants": [{
                 "firstName": "Donald",
                 "lastName": "Duck",
                 "fullName": "Donald Duck"
             }]}, {
               "beginDate": "2023-01-09T11:30:00+00:00",
               "endDate": "2023-01-09T15:00:00+00:00",
               "participants": [{
                 "firstName": "Dagobert",
                 "lastName": "Duck",
                 "fullName": "Dagobert Duck"
               }, {
                 "firstName": "Katrien",
                 "lastName": "Duck",
                 "fullName": "Katrien Duck"
             }]}
        ]}
    """
    today = datetime.date.today()
    room_duties = RoomDuty.objects.filter(begin__day=today.day, begin__month=today.month, begin__year=today.year).order_by('begin')
    result = []
    for room_duty in room_duties:
        single = {
            "beginDate": room_duty.begin.isoformat(),
            "endDate": room_duty.end.isoformat(),
            "participants": []
        }
        for participant in room_duty.participant_set.all():
            single['participants'].append({
                "firstName": participant.first_name,
                "lastName": participant.last_name,
                "fullName": participant.incomplete_name(),
            })
        result.append(single)

    return result

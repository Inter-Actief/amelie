import datetime
import random

from django.conf import settings
from django.utils import timezone
from jsonrpc import jsonrpc_method

from amelie.activities.models import Activity
from amelie.api.activitystream_utils import add_images_property, add_thumbnails_property
from amelie.api.decorators import authentication_optional
from amelie.api.utils import parse_datetime_parameter
from amelie.companies.models import TelevisionBanner, TelevisionVideo
from amelie.news.models import NewsItem
from amelie.narrowcasting.models import TelevisionPromotion
from amelie.room_duty.models import RoomDuty
from amelie.tools.templatetags import md


@jsonrpc_method('getBanners() -> Array', validate=True)
def get_narrowcasting_banners(request):
    result = []
    banners = TelevisionBanner.objects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now(), active=True)
    videos = TelevisionVideo.objects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now(), active=True)

    for banner in banners:
        result.append({
            "name": banner.name,
            "image": "%s%s" % (settings.MEDIA_URL, str(banner.picture)),
            "type": "image",
            "id": banner.id
        })
        
    for video in videos:
        result.append({
            "name": video.name,
            "videoId": video.video_id,
            "type": video.video_type,
            "id": video.id
        })

    return result


@jsonrpc_method('getNews(Number, Boolean) -> Array', validate=False)
def get_news(request, amount, render_markdown=False):
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


@jsonrpc_method('getTelevisionPromotions() -> Array', validate=True)
def get_television_promotions(request):
    result = []
    promotions = TelevisionPromotion.objects.filter(start__lte=timezone.now(), end__gte=timezone.now())

    for promotion in promotions:        
        res_dict = {
            "image": "%s%s" % (settings.MEDIA_URL, str(promotion.attachment))
        }

        if promotion.activity:
            res_dict["title"] = promotion.activity.summary
            if promotion.activity.enrollment:
                res_dict["signup"] = promotion.activity.enrollment
                res_dict["signupStart"] = promotion.activity.enrollment_begin.isoformat()
                res_dict["signupStop"] = promotion.activity.enrollment_end.isoformat()
                res_dict["signupMaximum"] = promotion.activity.maximum
                res_dict["signupAvailable"] = promotion.activity.places_available()

        result.append(res_dict)

    return result


@jsonrpc_method('getPhotos(Number, Number) -> Array', validate=True)
@authentication_optional()
def get_activity_photos(request, days, photos_per_activity, authentication=None):
    authenticated = authentication is not None
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


@jsonrpc_method('getHistoricActivitiesWithPictures(String, String, Number)', validate=True)
@authentication_optional()
def get_historic_activity_with_pictures(request, begin_date_string, end_date_string, amount, authentication=None):
    authenticated = authentication is not None
    begin_date = parse_datetime_parameter(begin_date_string)
    end_date = parse_datetime_parameter(end_date_string)

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
            "beginDate": activity.begin.isoformat(),
            "endDate": activity.end.isoformat(),
            "title": activity.summary,
            "location": activity.location,
            "source": "inter-actief",
            "id": activity.id,
            "url": activity.get_photo_url(),
        }

        add_thumbnails_property(activity, authentication, single)
        add_images_property(activity, authentication, single)

        result.append(single)

    return result


@jsonrpc_method('getRoomDutyToday()', validate=True)
@authentication_optional()
def get_room_duty_today(request, authentication=None):
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

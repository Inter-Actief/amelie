import logging
import requests
from django.conf import settings
from django.urls import reverse


logger = logging.getLogger(__name__)


def send_message(data):
    config = settings.DISCORD
    webhook_urls = []
    msg_data = {}

    if data['type'] == "activity":
        webhook_urls = config['activities_webhooks']
        msg_data = {
            'embeds': [
                {
                    'title': ":calendar: New {}! - {}".format(data['subtype'], data['title']),
                    'description': data['description'] + "\n\nMore info at the [Inter-_Actief_ website]({})".format(data['absolute_url']),
                    'type': "rich",
                    'url': data['absolute_url'],
                    'color': data['color'],
                    'image': {
                        'url': data['thumbnail']
                    } if data['thumbnail'] else None,
                    'thumbnail': {
                        'url': "https://huisstijl.ia.utwente.nl/assets/inter-actief-beeldmerk-wit-randloos.png"
                    },
                    'fields': [
                        {'name': "Organizer", 'value': data['organizer']},
                        {'name': "When?", 'value': data['date']},
                        {'name': "Where?", 'value': data['location']},
                    ]
                }
            ]
        }
    elif data['type'] == "news":
        webhook_urls = config['news_webhooks']
        msg_data = {
            'embeds': [
                {
                    'title': ":newspaper: New {}! - {}".format(data['subtype'], data['title']),
                    'description': data['intro'] + "\n\nRead more on the [Inter-_Actief_ website]({})".format(data['absolute_url']),
                    'type': "rich",
                    'url': data['absolute_url'],
                    'color': data['color'],
                    'image': {
                        'url': data['thumbnail']
                    } if data['thumbnail'] else None,
                    'thumbnail': {
                        'url': "https://huisstijl.ia.utwente.nl/assets/inter-actief-beeldmerk-wit-randloos.png"
                    },
                    'author': {
                        'name': "Posted by: " + data['committee']
                    }
                }
            ]
        }
    elif data['type'] == "photos":
        webhook_urls = config['pictures_webhooks']
        msg_data = {
            'embeds': [
                {
                    'title': ":camera::frame_photo: New {}! - {}".format(data['subtype'], data['title']),
                    'description': "There are {} photos ({} new) for the activity {}!\n\n"
                                   "View them on the [Inter-_Actief_ website]({})".format(
                        data['photo_count'], data['new_photo_count'], data['title'], data['absolute_url']
                    ),
                    'type': "rich",
                    'url': data['absolute_url'],
                    'color': data['color'],
                    'image': {
                        'url': data['thumbnail']
                    } if data['thumbnail'] else None,
                    'thumbnail': {
                        'url': "https://huisstijl.ia.utwente.nl/assets/inter-actief-beeldmerk-wit-randloos.png"
                    }
                }
            ]
        }

    for webhook_url in webhook_urls:
        logger.debug("Sending discord message to webhook {} - {}".format(webhook_url, msg_data))
        res = requests.post(webhook_url, json=msg_data)
        logger.debug("Result: {}".format(str(res)))


def send_discord(sender, **kwargs):
    from amelie.news.models import NewsItem
    from amelie.activities.models import Activity
    from amelie.companies.models import CompanyEvent
    from amelie.education.models import EducationEvent

    instance = kwargs.get('instance')
    created = kwargs.get("created")

    if sender in [NewsItem, Activity, CompanyEvent, EducationEvent]:
        data = {
            'type': None,
            'color': 0x077821,
            'thumbnail': None
        }

        if sender == NewsItem:
            if created:
                committee = instance.publisher.name
                absolute_url = instance.get_absolute_url()
                title = instance.title_en if instance.title_en else instance.title_nl
                intro = instance.introduction_en if instance.introduction_en else instance.introduction_nl

                # Construct message
                data['type'] = "news"
                data['subtype'] = "News"
                data['committee'] = committee if committee else "Unknown"
                data['title'] = title if title else "Unknown"
                data['intro'] = intro if intro else "Unknown"
                data['absolute_url'] = "https://www.inter-actief.utwente.nl{}".format(absolute_url) if absolute_url else ""
                if instance.is_education_item:
                    data['color'] = 0x077821

        elif sender == Activity:
            if created:
                entire_day = instance.entire_day
                begin = instance.begin.strftime('%a %d-%m-%Y %H:%M')
                end = instance.end.strftime('%a %d-%m-%Y %H:%M')
                absolute_url = instance.get_absolute_url()
                organizer = instance.organizer.name
                title = instance.summary_en if instance.summary_en else instance.summary_nl
                location = instance.location
                if len(instance.promo_en) > 64:
                    description = instance.promo_en
                else:
                    description = instance.description_en or instance.description_nl

                if instance.image_icon:
                    if str(instance.image_icon.url).startswith("https://") or str(instance.image_icon.url).startswith("http://"):
                        data['thumbnail'] = str(instance.image_icon.url)
                    else:
                        data['thumbnail'] = "https://www.inter-actief.utwente.nl{}".format(str(instance.image_icon.url))

                # Construct message
                data['type'] = "activity"
                data['subtype'] = "Activity"
                data['organizer'] = organizer if organizer else "Unknown"
                data['date'] = "the entire day" if entire_day else "from {} until {}".format(begin, end)
                data['title'] = title if title else "Unknown"
                data['description'] = description if description else "No description"
                data['location'] = location if location else "Unknown"
                data['absolute_url'] = "https://www.inter-actief.utwente.nl{}".format(absolute_url) if absolute_url else ""
                data['color'] = 0x077821

        elif sender == CompanyEvent:
            if created and instance.is_visible():
                entire_day = instance.entire_day
                begin = instance.begin.strftime('%a %d-%m-%Y %H:%M')
                end = instance.end.strftime('%a %d-%m-%Y %H:%M')
                absolute_url = instance.get_absolute_url()
                organizer = instance.company.name if instance.company else instance.company_text
                title = instance.summary_en if instance.summary_en else instance.summary_nl
                location = instance.location
                description = instance.description_en or instance.description_nl

                # Construct message
                data['type'] = "activity"
                data['subtype'] = "Company Activity"
                data['organizer'] = organizer if organizer else "Unknown"
                data['date'] = "the entire day" if entire_day else "from {} until {}".format(begin, end)
                data['title'] = title if title else "Unknown"
                data['description'] = description if description else "No description"
                data['location'] = location if location else "Unknown"
                data['absolute_url'] = "https://www.inter-actief.utwente.nl{}".format(absolute_url) if absolute_url else ""
                data['color'] = 0x1D428A

        elif sender == EducationEvent:
            if created:
                entire_day = instance.entire_day
                begin = instance.begin.strftime('%a %d-%m-%Y %H:%M')
                end = instance.end.strftime('%a %d-%m-%Y %H:%M')
                absolute_url = instance.get_absolute_url()
                organizer = instance.education_organizer
                title = instance.summary_en if instance.summary_en else instance.summary_nl
                location = instance.location
                description = instance.description_en or instance.description_nl

                # Construct message
                data['type'] = "activity"
                data['subtype'] = "Educational Activity"
                data['organizer'] = organizer if organizer else "Unknown"
                data['date'] = "the entire day" if entire_day else "from {} until {}".format(begin, end)
                data['title'] = title if title else "Unknown"
                data['description'] = description if description else "No description"
                data['location'] = location if location else "Unknown"
                data['absolute_url'] = "https://www.inter-actief.utwente.nl{}".format(absolute_url) if absolute_url else ""
                data['color'] = 0xB8231F

        # Only send the message if we actually have one.
        if data['type'] is not None:
            # Send message
            send_message(data)


def send_discord_presave(sender, **kwargs):
    from amelie.activities.models import Activity

    instance = kwargs.get('instance')

    try:
        original = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return  # New object

    data = {
        'type': None,
        'color': 0x077821,
        'thumbnail': None
    }

    if sender == Activity:
        # If there are more pictures then before, send a notification
        if len(instance.photos.all()) > len(original.photos.all()):
            title = instance.summary_en if instance.summary_en else instance.summary_nl

            picture_url = None
            random_picture = instance.random_photo(only_public=True)
            if random_picture is not None:
                picture_url = random_picture.thumb_medium if random_picture.thumb_medium else None
                if picture_url is None:
                    picture_url = random_picture.thumb_large if random_picture.thumb_large else None
                if picture_url is None:
                    picture_url = random_picture.file if random_picture.file else None
                picture_url = "{}{}".format(settings.MEDIA_URL, picture_url)

            # Construct message
            data['type'] = "photos"
            data['subtype'] = "Photos"
            data['title'] = title if title else "Unknown"
            photos_url = reverse("activities:gallery", kwargs={'pk': instance.pk})
            data['absolute_url'] = "https://www.inter-actief.utwente.nl{}".format(photos_url)
            data['photo_count'] = len(instance.photos.all())
            data['new_photo_count'] = len(instance.photos.all()) - len(original.photos.all())
            data['thumbnail'] = picture_url

    # Only send the message if we actually have one.
    if data['type'] is not None:
        # Send message
        send_message(data)

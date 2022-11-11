import random
from django.conf import settings

from amelie.activities.models import Activity, EnrollmentoptionQuestion, EnrollmentoptionCheckbox, \
    EnrollmentoptionFood
from amelie.api.common import strip_markdown
from amelie.companies.models import CompanyEvent
from amelie.calendar.models import Participation
from amelie.education.models import EducationEvent
from amelie.tools.templatetags import md


# Returns basic event properties
def get_basic_result(activity):
    result = {
        "id": activity.id,
        "beginDate": activity.begin.isoformat(),
        "endDate": activity.end.isoformat(),
        "title": activity.summary,
        "location": activity.location,
        "category": activity.activity_type,
        "url": activity.get_absolute_url(),
        "isDutch": activity.dutch_activity,
    }

    if type(activity) == EducationEvent:
        result["organizer"] = activity.education_organizer
    elif type(activity) == CompanyEvent:
        result["organizer"] = activity.company.name if activity.company else activity.company_text
    else:
        result["organizer"] = activity.organizer.name

    return result


# Add detailed properties to a result item
def add_detailed_properties(activity, authentication, result):
    authenticated = authentication is not None

    result["description"] = strip_markdown(activity.description)
    result["html"] = md.markdown(activity.description)

    if type(activity) == Activity:
        result["imageUrl"] = activity.image_icon.url if activity.image_icon else None
        result["signupRequired"] = activity.enrollment
        result["price"] = activity.price
        result["signupStart"] = activity.enrollment_begin.isoformat() if activity.enrollment_begin else None
        result["signupStop"] = activity.enrollment_end.isoformat() if activity.enrollment_end else None
        result["availability"] = activity.maximum if activity.maximum is not None else 0
        result["signupAvailable"] = activity.enrollment and activity.enrollment_open() \
                                    and not activity.enrollment_full()
        result["signupWaitinglist"] = activity.enrollment_full()
        result["resignAvailable"] = activity.enrollment and activity.enrollment_open() \
                                    and activity.can_unenroll
        result["signedUp"] = authentication.represents() in activity.participants.all() if authenticated else False

        if authenticated and result["signedUp"]:
            result["price"], with_costs = Participation.objects.get(person=authentication.represents(),
                                                                    event=activity).calculate_costs()

        add_options_property(activity, authentication, result)


# Add options property to a result item
def add_options_property(activity, authentication, result):
    if type(activity) != Activity:
        return

    result["options"] = []

    if authentication is not None:
        for option in activity.enrollmentoption_set.all():
            if option.content_type.model_class() == EnrollmentoptionQuestion:
                result["options"].append({
                    "question": option.title,
                    "type": "question",
                    "id": option.id,
                    "required": option.required,
                })
            elif option.content_type.model_class() == EnrollmentoptionCheckbox:
                result["options"].append({
                    "question": option.title,
                    "type": "checkbox",
                    "id": option.id,
                    "price": option.price_extra,
                })
            elif option.content_type.model_class() == EnrollmentoptionFood:
                dishes = option.dishprice_set.all()
                choices = []
                for choice in dishes:
                    choices.append({
                        "id": choice.id,
                        "price": choice.price,
                        "dish": choice.dish.name,
                        "restaurant": choice.dish.restaurant.name,
                    })
                result["options"].append({
                    "question": option.title,
                    "type": "selectbox",
                    "id": option.id,
                    "choices": choices,
                    "required": option.required,
                })


# Add thumbnails property to a result item
def add_thumbnails_property(activity, authentication, result):
    if type(activity) != Activity:
        return

    authenticated = authentication is not None
    photos = activity.photos.filter_public(not authenticated)

    result["thumbnails"] = {
        "small": None,
        "medium": None,
        "large": None,
        "original": None
    }

    if photos.count() > 0:
        photo = random.choice(photos)

        result["thumbnails"] = {
            "small": "{}{}".format(settings.MEDIA_URL, photo.thumb_small) if photo.thumb_small else None,
            "medium": "{}{}".format(settings.MEDIA_URL, photo.thumb_medium) if photo.thumb_medium else None,
            "large": "{}{}".format(settings.MEDIA_URL, photo.thumb_large) if photo.thumb_large else None,
            "original": "{}{}".format(settings.MEDIA_URL, photo.file)
        }


# Add images property to a result item
def add_images_property(activity, authentication, result):
    if type(activity) != Activity:
        return

    authenticated = authentication is not None
    photos = activity.photos.filter_public(not authenticated)

    result["images"] = []

    for photo in photos:
        if photo.file:
            result["images"].append({
                "small": "%s%s" % (settings.MEDIA_URL, photo.thumb_small if photo.thumb_small else None),
                "medium": "%s%s" % (settings.MEDIA_URL, photo.thumb_medium if photo.thumb_medium else None),
                "large": "%s%s" % (settings.MEDIA_URL, photo.thumb_large if photo.thumb_large else None),
                "original": "%s%s" % (settings.MEDIA_URL, photo.file),
            })

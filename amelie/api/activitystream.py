from decimal import Decimal
from itertools import chain
import logging
import operator
from typing import List, Dict

from modernrpc import RpcRequestContext

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from amelie.activities.mail import activity_send_enrollmentmail, activity_send_on_waiting_listmail
from amelie.activities.models import Activity, EnrollmentoptionQuestion, EnrollmentoptionCheckbox, EnrollmentoptionFood
from amelie.activities.models import EnrollmentoptionQuestionAnswer, EnrollmentoptionCheckboxAnswer, \
    EnrollmentoptionFoodAnswer
from amelie.activities.utils import update_waiting_list
from amelie.api.api import api_server
from amelie.api.activitystream_utils import add_detailed_properties, add_images_property, add_thumbnails_property, \
    get_basic_result
from amelie.api.authentication_types import AnonymousAuthentication
from amelie.api.decorators import auth_optional, auth_required
from amelie.api.exceptions import NotLoggedInError, MissingOptionError, SignupError, DoesNotExistError
from amelie.api.utils import parse_datetime_parameter
from amelie.companies.models import CompanyEvent
from amelie.calendar.models import Participation
from amelie.education.models import EducationEvent
from amelie.personal_tab import transactions


logger = logging.getLogger(__name__)


@api_server.register_procedure(name='getActivityStream', auth=auth_optional, context_target='ctx')
def get_activity_stream(begin_date_str: str, end_date_str: str, return_mixed: bool = False, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves a combined list of _regular_, _educational_ and _external_ activities.
    If authenticated, also non-public activities will be returned.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - begin_date_str: The minimal end date, RFC3339 (inclusive)
        - end_date_str: The maximal begin date, RFC3339 (exclusive)
        - return_mixed: Boolean value indicating whether the client supports a result of mixed activity
                        types, OPTIONAL, default false. If true only regular activities are returned.

    **Return:**
      `List[Dict]`: An array of dictionaries containing activity info.

      Each returned element in the list has the following fields:

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

    **Raises:**

      InvalidParamsError: One of the date parameters was not in a valid RFC3339 format.

    **Example:**

        --> {"method": "getActivityStream", "params": ["2014-07-01T00:00:00+02:00", "2014-07-31T23:59:59+02:00", true]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false
                }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)
    begin_date = parse_datetime_parameter(begin_date_str)
    end_date = parse_datetime_parameter(end_date_str)

    # Regular activities
    regular_activities = Activity.objects.filter_public(not is_authenticated)\
        .filter(end__gt=begin_date, begin__lte=end_date)

    # Educational activities
    education_activities = EducationEvent.objects.filter_public(not is_authenticated) \
        .filter(end__gt=begin_date, begin__lte=end_date)

    # External activities
    external_activities = CompanyEvent.objects.filter_public(not is_authenticated) \
        .filter(end__gt=begin_date, begin__lte=end_date,
                visible_from__lte=timezone.now(), visible_till__gte=timezone.now())

    activities = chain(regular_activities, education_activities, external_activities)\
        if return_mixed else regular_activities
    ordered_activities = sorted(activities, key=operator.attrgetter("begin"))

    result = []
    for activity in ordered_activities:
        single = get_basic_result(activity)
        result.append(single)
    return result


@api_server.register_procedure(name='getUpcomingActivities', auth=auth_optional, context_target='ctx')
def get_upcoming_activities(amount: int, return_mixed: bool = False, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves a list of upcoming activities, nearest first.
    If authenticated, also non-public activities will be returned.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - amount: The amount of activities
        - return_mixed: Boolean value indicating whether the client supports a result of mixed activity
                        types, OPTIONAL, default false. If true only regular activities are returned.

    **Return:**
      `List[Dict]`: An array of dictionaries containing activity info.

      Each returned element in the list has the same fields as the `getActivityStream` method:

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

    **Example:**

        --> {"method": "getUpcomingActivities", "params": [50, true]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false
                }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)

    # Regular activities
    regular_activities = Activity.objects.filter_public(not is_authenticated).filter(begin__gte=timezone.now())

    # Educational activities
    education_activities = EducationEvent.objects.filter_public(not is_authenticated).filter(begin__gte=timezone.now())

    # External activities
    external_activities = CompanyEvent.objects.filter_public(not is_authenticated)\
        .filter(begin__gte=timezone.now(), visible_from__lte=timezone.now(), visible_till__gte=timezone.now())

    activities = chain(regular_activities, education_activities, external_activities)\
        if return_mixed else regular_activities
    ordered_activities = sorted(activities, key=operator.attrgetter("begin"))

    result = []
    for activity in ordered_activities[0:amount]:
        single = get_basic_result(activity)
        result.append(single)
    return result


@api_server.register_procedure(name='getActivityDetailed', auth=auth_optional, context_target='ctx')
def get_activity_detail(activity_id: int, ctx: RpcRequestContext = None, **kwargs) -> Dict:
    """
    Retrieves details of an event, including its signup options if available.
    If authenticated, also details of non-public activities can be requested.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - activity_id: The id of the requested activity

    **Return:**
      `Dict`: A dictionary containing detailed activity info.

      Each returned element in the list has the same fields as the `getActivityStream` method, plus some extra fields:

      Basic information (same as `getActivityStream`):

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

      Extra fields (all activities):

        - description: The description of this activity, as plain text.
        - html: The description of this activity, in HTML format.

      Extra fields (only activities with category `regular`):

        - imageUrl: An URL to the graphic attached to this activity, can be null
        - signupRequired: true if signup is required, otherwise false
        - price: The base costs for enrollment, or total costs when signed up, 0 if no price
        - signupStart: The time at which enrollment opens (RFC3339)
        - signupStop: The time at which enrollment closes (RFC3339)
        - availability: The maximum amount of attendees, 0 if no maximum
        - signupAvailable: true if it is possible to sign up, otherwise false
        - signupWaitinglist: true if there are no more places available and if there is a maximum, otherwise false
        - resignAvailable: true if it is possible to sign out, otherwise false
        - signedUp: true if logged in and signed up, otherwise false
        - options: An array of dictionaries representing signup options, or empty array if there are no signup options:
          - id: The ID of this option
          - type: Type of option, either "question", "checkbox" or "selectbox"
          - question: The description of this option
          - price: Additional costs, only present for the checkbox type
          - required: True if this question or selectbox requires an answer.
          - choices: Array of dictionaries representing choices for the selectbox:
            - id: The ID of this choice
            - dish: The dish name of this choice
            - restaurant: The restaurant name of this choice
            - price: The additional costs of this choice
        - thumbnails: A dictionary with the following properties:
          - small: An URL to the small thumbnail, can be null
          - medium: An URL to the medium thumbnail, can be null
          - large: An URL to the large thumbnail, can be null
          - original: An URL to the original thumbnail, can be null
        - images: An array of dictionaries representing pictures for this activity, or an empty array:
          - small: An URL to the small picture, can be null
          - medium: An URL to the medium picture, can be null
          - large: An URL to the large picture, can be null
          - original: An URL to the original picture, can be null

    **Raises:**

      NotLoggedInError: If the activity is private and no authentication was given, or the authentication was invalid.
      DoesNotExistError: If the requested activity does not exist.

    **Example:**

        --> {"method": "getActivityDetailed", "params": [28]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false,

                "description": "Super cool awesome activity with pizza!",
                "html": "<p>Super cool awesome activity with pizza!</p>",

                "imageUrl": "https://pic0",
                "signupRequired": true,
                "availability": 50,
                "signupStart": "2014-07-02T018:00:00+02:00",
                "signupStop": "2014-07-02T018:00:00+02:00",
                "signedUp": false,
                "resignAvailable": true,
                "signupAvailable": true,
                "price": 50.00,
                "thumbnails": {
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                },
                "images": [{
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                }, {...}, ...],
                "options": [
                  {
                    "id":123,
                    "type": "selectbox",
                    "question": "What kind of pizza? (Joe Pizza)",
                    "required": true,
                    "choices": [
                      {"id":87, "dish": "Hawaii", "restaurant": "Joe Pizza", "price":6.0},
                      {"id":88, "dish": "Salami", "restaurant": "Joe Pizza", "price":7.0}
                    ]
                  }, {
                    "id":124,
                    "type": "checkbox",
                    "question": "Super priority delivery",
                    "price": 2.0
                  }, {
                    "id":125,
                    "type": "question",
                    "question": "What is your mothers maiden name?",
                    "required": true
                  }, {...}, ...
                ]
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)

    # Check if activity exists
    try:
        activities = chain(Activity.objects.all(), EducationEvent.objects.all(), CompanyEvent.objects.all())
        activity = next(x for x in activities if x.id == activity_id)
    except StopIteration:
        raise DoesNotExistError()

    # Check if the activity is public and if the user is authenticated
    if not activity.public and not is_authenticated:
        raise NotLoggedInError()

    result = get_basic_result(activity)
    add_detailed_properties(activity, authentication, result)
    add_thumbnails_property(activity, authentication, result)
    add_images_property(activity, authentication, result)
    return result


@api_server.register_procedure(name='getActivityThumbnailsStream', auth=auth_optional, context_target='ctx')
def get_activity_thumbnails_stream(begin_date_str: str, end_date_str: str, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves a list of basic information of activities with pictures, and their thumbnail images.
    If authenticated, also non-public activities will be returned.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - begin_date_str: The minimal end date, RFC3339 (inclusive)
        - end_date_str: The maximal begin date, RFC3339 (exclusive)

    **Return:**
      `List[Dict]`: An array of dictionaries containing activity and thumbnail info.

      Each returned element in the list has the same fields as the `getActivityStream` method, and thumbnail URLs:

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

        - thumbnails: A dictionary with the following properties:
          - small: An URL to the small thumbnail, can be null
          - medium: An URL to the medium thumbnail, can be null
          - large: An URL to the large thumbnail, can be null
          - original: An URL to the original thumbnail, can be null

    **Raises:**

      InvalidParamsError: One of the date parameters was not in a valid RFC3339 format.

    **Example:**

        --> {"method": "getActivityThumbnailsStream", "params": ["2014-07-01T00:00:00+02:00", "2014-07-31T23:59:59+02:00"]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false,
                "thumbnails": {
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                }
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)
    begin_date = parse_datetime_parameter(begin_date_str)
    end_date = parse_datetime_parameter(end_date_str)

    regular_activities = Activity.objects.filter_public(not is_authenticated) \
        .filter(photos__gt=0, end__gt=begin_date, begin__lte=end_date).distinct()

    if not is_authenticated:
        regular_activities = regular_activities.filter(photos__public=True)

    result = []
    for activity in regular_activities:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        result.append(single)
    return result


@api_server.register_procedure(name='getLatestActivitiesWithPictures', auth=auth_optional, context_target='ctx')
def get_latest_activities_with_pictures(amount: int, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves a list of most recent activities with pictures, and their associated pictures.
    If authenticated, also non-public activities will be returned.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - amount: The amount of activities to return

    **Return:**
      `List[Dict]`: An array of dictionaries containing activity and picture info.

      Each returned element in the list has the same fields as the `getActivityStream` method, and picture details:

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

        - thumbnails: A dictionary with the following properties:
          - small: An URL to the small thumbnail, can be null
          - medium: An URL to the medium thumbnail, can be null
          - large: An URL to the large thumbnail, can be null
          - original: An URL to the original thumbnail, can be null
        - images: An array of dictionaries representing pictures for this activity, or an empty array:
          - small: An URL to the small picture, can be null
          - medium: An URL to the medium picture, can be null
          - large: An URL to the large picture, can be null
          - original: An URL to the original picture, can be null

    **Raises:**

      InvalidParamsError: One of the date parameters was not in a valid RFC3339 format.

    **Example:**

        --> {"method": "getLatestActivitiesWithPictures", "params": [50]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false,
                "thumbnails": {
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                },
                "images": [{
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                }, {...}, ...],
              }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)

    activities = Activity.objects.filter_public(not is_authenticated).filter(photos__gt=0).distinct().order_by("-begin")

    if not is_authenticated:
        activities = activities.filter(photos__public=True)

    result = []
    for activity in activities[0:amount]:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        add_images_property(activity, authentication, single)
        result.append(single)
    return result


@api_server.register_procedure(name='searchGallery', auth=auth_optional, context_target='ctx')
def search_gallery(query: str, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Search all activity titles of activities with pictures for a query string.
    If authenticated, also non-public activities will be searched.

    **Module**: `activitystream`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - query: The search query (not case-sensitive), results are only returned if query is 3 or more characters long.

    **Return:**
      `List[Dict]`: An array of dictionaries containing the search results.

      Each returned element in the list has the same fields as the `getActivityStream` method,
      thumbnail details and the amount of photos:

        - id: The identifier for this activity
        - title: The title of this activity
        - beginDate: The starting date and time of this activity (RFC3339)
        - endDate: The end date and time of this activity (RFC3339)
        - location: The location of this activity
        - category: The type of this activity (either "regular", "educational" or "external")
        - url: The URL for this activity
        - organizer: The organizer of this activity
        - isDutch: A boolean value indicating if the activity is Dutch-only

        - thumbnails: A dictionary with the following properties:
          - small: An URL to the small thumbnail, can be null
          - medium: An URL to the medium thumbnail, can be null
          - large: An URL to the large thumbnail, can be null
          - original: An URL to the original thumbnail, can be null
        - photoCount: The amount of pictures available for this activity

    **Example:**

        --> {"method": "searchGallery", "params": ["project"]}
        <-- {"result": [
              {
                "id": 28,
                "title": "Project Evening",
                "beginDate": "2014-07-02T018:00:00+02:00",
                "endDate": "2014-07-03T08:00:00+02:00",
                "location": "Carre 2K",
                "category": "regular",
                "url": "/activities/28/",
                "organizer": "Board",
                "isDutch": false,
                "thumbnails": {
                  "small": "https://pic1/small/",
                  "medium": "https://pic1/medium/",
                  "large": "https://pic1/large/",
                  "original": "https://pic1/original/"
                },
                "photoCount": 27
                }, {...}, ...]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)
    result = []

    # Deny all results with queries that consist of less than 3 characters so that the server
    if len(query) < 3:
        return result

    activities = list(reversed(Activity.objects.filter_public(not is_authenticated).filter(photos__gt=0).filter(
        Q(summary_nl__icontains=query) | Q(summary_en__icontains=query)
    ).distinct()))

    for activity in activities:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        single["photoCount"] = len(activity.photos.filter_public(not is_authenticated))
        result.append(single)

    return result


@api_server.register_procedure(name='activitySignup', auth=auth_required('signup'), context_target='ctx')
@transaction.atomic
def activity_signup(activity_id: int, price: float, options: dict, ctx: RpcRequestContext = None, **kwargs) -> bool:
    """
    Enrolls the current user as attendee to an activity.

    **Module**: `activitystream`

    **Authentication:** REQUIRED (Scope: signup)

    **Parameters:**
      This method accepts the following parameters:

        - activity_id: The ID of the activity
        - price: The calculated costs, used for consistency checks (decimal)
        - options: An array of dictionaries representing the selected options. Unanswered options
                   should be omitted. All options with the "required" attribute MUST be present:
          - id: The ID of the option
          - value: The value of the option; A string for a "question", boolean for "checkbox", integer for "selectbox".

    **Return:**
      `bool`: `true` if successfully signed up, otherwise an error.

    **Raises:**

      DoesNotExistError: The activity with this ID does not exist.
      NotLoggedInError: Invalid or no authentication token received
      SignupError: User could not be signed up. See the error message for more details.
      MissingOptionError: Occurs when not all required options were present.

    **Example:**

        --> {"method": "activitySignup", "params": [
              28,
              56.0,
              [{"id": 123, "value": 87}, {"id": 125, "value": "Wortel"}]
            ]}
        <-- {"result": true}
    """
    authentication = ctx.auth_result

    optionset = {}
    for option in options:
        if isinstance(option, dict) and "id" in option.keys() and "value" in option.keys() and option["value"]:
            optionset[option["id"]] = option["value"]

    try:
        # Lock the Activity object for updating, prevent concurrent (un)enrollments
        activity = Activity.objects.select_for_update().get(id=activity_id)
    except Activity.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if activity.oauth_application and not activity.oauth_application == authentication.get_application():
        raise SignupError("You can only subscribe to this activity on the website of this activity.")
    elif not authentication.represents():
        raise SignupError("Could not determine who you are based on your login credentials.")
    elif authentication.represents() in activity.participants.all():
        raise SignupError("You are already signed up for this activity")
    elif not activity.enrollment:
        raise SignupError("You cannot sign up for this activity, there is no subscription.")
    elif not activity.enrollment_open():
        raise SignupError("You cannot sign up for this activity, the subscription is not open")

    # check if all required options are present and filled in
    for option in activity.enrollmentoption_set.all():
        if option.content_type.model_class() == EnrollmentoptionQuestion and option.required and \
                (option.id not in optionset.keys() or not optionset[option.id]):
            raise MissingOptionError()
        elif option.content_type.model_class() == EnrollmentoptionFood and option.required and \
                (option.id not in optionset.keys() or not isinstance(optionset[option.id], int)
                 or not option.dishprice_set.filter(id=optionset[option.id]).exists()):
            raise MissingOptionError()

    # save attendance
    attendance = Participation(event=activity,
                               person=authentication.represents(),
                               remark='Enrollment through OAuth',
                               payment_method=Participation.PaymentMethodChoices.NONE,
                               added_by=authentication.represents(),
                               waiting_list=activity.enrollment_full())
    attendance.save()

    # save options
    for option in activity.enrollmentoption_set.all():
        answer = None
        if option.content_type.model_class() == EnrollmentoptionQuestion:
            result = optionset[option.id] if option.id in optionset.keys() else ''
            answer = EnrollmentoptionQuestionAnswer(answer=result, enrollment=attendance, enrollmentoption=option)
        elif option.content_type.model_class() == EnrollmentoptionCheckbox:
            result = option.id in optionset.keys() and optionset[option.id]
            answer = EnrollmentoptionCheckboxAnswer(answer=result, enrollment=attendance, enrollmentoption=option)
        elif option.content_type.model_class() == EnrollmentoptionFood:
            result = option.dishprice_set.get(id=optionset[option.id]) if option.id in optionset.keys() else None
            answer = EnrollmentoptionFoodAnswer(dishprice=result, enrollment=attendance, enrollmentoption=option)

        if answer:
            answer.content_type = ContentType.objects.get_for_model(answer)
            answer.save()

    # check for inconsistency in app
    amount, with_options = attendance.calculate_costs()
    if abs(Decimal(price) - amount) > 0.02:  # allow for floating point precision bugs
        raise SignupError("An inconsistency was detected. Please use the website to sign up.")

    # Check if a payment is needed.
    if amount:
        # Check if the person has a signed mandate.
        if not authentication.represents().has_mandate_activities():
            raise SignupError("A signed mandate is required. Please ask the board for a mandate.")

        # Set payment by direct debit.
        attendance.payment_method = Participation.PaymentMethodChoices.AUTHORIZATION
        attendance.save()

        if not activity.enrollment_full():
            # add transaction
            transactions.add_participation(attendance, authentication.represents())

        # Send mail if desired
        if authentication.represents().has_preference(name='mail_enrollment'):
            if not activity.enrollment_full():
                activity_send_enrollmentmail(attendance)
            else:
                activity_send_on_waiting_listmail(attendance)

    return True


@api_server.register_procedure(name='activityRevokeSignup', auth=auth_required('signup'), context_target='ctx')
@transaction.atomic
def activity_signup_revoke(activity_id: int, ctx: RpcRequestContext = None, **kwargs) -> bool:
    """
    Un-enrolls the current user as attendee from an activity.

    **Module**: `activitystream`

    **Authentication:** REQUIRED (Scope: signup)

    **Parameters:**
      This method accepts the following parameters:

        - activity_id: The ID of the activity

    **Return:**
      `bool`: `true` if successfully revoked, otherwise an error.

    **Raises:**

      DoesNotExistError: The activity with the given ID does not exist.
      NotLoggedInError: Invalid or no authentication token received.
      SignupError: User could not be un-enrolled. See the error message for more details.

    **Example:**

        --> {"method": "activityRevokeSignup", "params": [28]}
        <-- {"result": true}
    """
    authentication = ctx.auth_result

    try:
        # Lock the Activity object for updating, prevent concurrent (un)enrollments
        activity = Activity.objects.select_for_update().get(id=activity_id)
    except Activity.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if activity.oauth_application and not activity.oauth_application == authentication.get_application():
        raise SignupError("You can only unsubscribe to this activity on the website of this activity.")
    elif not activity.enrollment:
        raise SignupError("You cannot unsubscribe for this activity, it has no subscription.")
    elif not authentication.represents():
        raise SignupError("Could not determine who you are based on your login credentials.")
    elif not authentication.represents() in activity.participants.all():
        raise SignupError("You were not subscribed for this activity.")
    elif not activity.can_unenroll:
        raise SignupError(
            "You cannot revoke your attendance anymore, it is not possible to unsubscribe for this activity.")
    elif not activity.enrollment_open():
        raise SignupError("You cannot revoke your attendance anymore, subscription term has expired.")

    attendance = Participation.objects.select_for_update().get(person=authentication.represents(),
                                                               event=activity)

    # If necessary, create a compensation for attendance
    transactions.remove_participation(attendance)

    # Delete attendance
    attendance.delete()

    update_waiting_list(activity=activity)

    return True

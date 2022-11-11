import logging
import operator

from decimal import Decimal
from itertools import chain

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from jsonrpc import jsonrpc_method

from amelie.activities.mail import activity_send_enrollmentmail, activity_send_on_waiting_listmail
from amelie.activities.models import Activity, EnrollmentoptionQuestion, EnrollmentoptionCheckbox, EnrollmentoptionFood
from amelie.activities.models import EnrollmentoptionQuestionAnswer, EnrollmentoptionCheckboxAnswer, \
    EnrollmentoptionFoodAnswer
from amelie.activities.utils import update_waiting_list
from amelie.api.activitystream_utils import add_detailed_properties, add_images_property, add_thumbnails_property, \
    get_basic_result
from amelie.api.decorators import authentication_optional, authentication_required
from amelie.api.exceptions import NotLoggedInError, MissingOptionError, SignupError, DoesNotExistError
from amelie.api.utils import parse_datetime_parameter
from amelie.companies.models import CompanyEvent
from amelie.calendar.models import Participation
from amelie.education.models import EducationEvent
from amelie.personal_tab import transactions

logger = logging.getLogger(__name__)


@jsonrpc_method('getActivityStream(String, String, Boolean) -> Array', validate=False)
def get_activity_stream(request, begin_date_string, end_date_string, return_mixed=False):
    return get_activity_stream_result(request, begin_date_string, end_date_string, return_mixed)


@authentication_optional()
def get_activity_stream_result(request, begin_date_string, end_date_string, return_mixed, authentication=None):
    authenticated = authentication is not None
    begin_date = parse_datetime_parameter(begin_date_string)
    end_date = parse_datetime_parameter(end_date_string)

    # Regular activities
    regular_activities = Activity.objects.filter_public(not authenticated)\
        .filter(end__gt=begin_date, begin__lte=end_date)

    # Educational activities
    education_activities = EducationEvent.objects.filter_public(not authenticated) \
        .filter(end__gt=begin_date, begin__lte=end_date)

    # External activities
    external_activities = CompanyEvent.objects.filter_public(not authenticated) \
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


@jsonrpc_method('getUpcomingActivities(Number, Boolean) -> Array', validate=False)
def get_upcoming_activities(request, amount, return_mixed=False):
    return get_upcoming_activities_result(request, amount, return_mixed)


@authentication_optional()
def get_upcoming_activities_result(request, amount, return_mixed, authentication=None):
    authenticated = authentication is not None

    # Regular activities
    regular_activities = Activity.objects.filter_public(not authenticated).filter(begin__gte=timezone.now())

    # Educational activities
    education_activities = EducationEvent.objects.filter_public(not authenticated).filter(begin__gte=timezone.now())

    # External activities
    external_activities = CompanyEvent.objects.filter_public(not authenticated)\
        .filter(begin__gte=timezone.now(), visible_from__lte=timezone.now(), visible_till__gte=timezone.now())

    activities = chain(regular_activities, education_activities, external_activities)\
        if return_mixed else regular_activities
    ordered_activities = sorted(activities, key=operator.attrgetter("begin"))

    result = []
    for activity in ordered_activities[0:amount]:
        single = get_basic_result(activity)
        result.append(single)
    return result


@jsonrpc_method('getActivityDetailed(Number) -> Object', validate=True)
@authentication_optional()
def get_activity_detail(request, id, authentication=None):
    # Check if activity exists
    try:
        activities = chain(Activity.objects.all(), EducationEvent.objects.all(), CompanyEvent.objects.all())
        activity = next(x for x in activities if x.id == id)
    except StopIteration:
        raise DoesNotExistError()

    # Check if the activity is public and if the user is authenticated
    if not activity.public and authentication is None:
        raise NotLoggedInError()

    result = get_basic_result(activity)
    add_detailed_properties(activity, authentication, result)
    add_thumbnails_property(activity, authentication, result)
    add_images_property(activity, authentication, result)
    return result


@jsonrpc_method('getActivityThumbnailsStream(String, String)', validate=True)
@authentication_optional()
def get_activity_thumbnails_stream(request, begin_date_string, end_date_string, authentication=None):
    authenticated = authentication is not None
    begin_date = parse_datetime_parameter(begin_date_string)
    end_date = parse_datetime_parameter(end_date_string)

    regular_activities = Activity.objects.filter_public(not authenticated) \
        .filter(photos__gt=0, end__gt=begin_date, begin__lte=end_date).distinct()

    if not authenticated:
        regular_activities = regular_activities.filter(photos__public=True)

    result = []
    for activity in regular_activities:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        result.append(single)
    return result


@jsonrpc_method('getLatestActivitiesWithPictures(Number) -> Array', validate=True)
@authentication_optional()
def get_latest_activities_with_pictures(request, amount, authentication=None):
    authenticated = authentication is not None

    activities = Activity.objects.filter_public(not authenticated).filter(photos__gt=0).distinct().order_by("-begin")

    if not authenticated:
        activities = activities.filter(photos__public=True)

    result = []
    for activity in activities[0:amount]:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        add_images_property(activity, authentication, single)
        result.append(single)
    return result


@jsonrpc_method('searchGallery(String)', validate=True)
@authentication_optional()
def search_gallery(request, query, authentication=None):
    authenticated = authentication is not None
    result = []

    # Deny all results with queries that consist of less than 3 characters so that the server
    if len(query) < 3:
        return result

    activities = list(reversed(Activity.objects.filter_public(not authenticated).filter(photos__gt=0).filter(
        Q(summary_nl__icontains=query) | Q(summary_en__icontains=query)
    ).distinct()))

    for activity in activities:
        single = get_basic_result(activity)
        add_thumbnails_property(activity, authentication, single)
        single["photoCount"] = len(activity.photos.filter_public(not authenticated))
        result.append(single)

    return result


@jsonrpc_method('activitySignup(Number, Number, Array) -> Boolean', validate=True)
@transaction.atomic
@authentication_required('signup')
def activity_signup(request, activity_id, price, options, authentication=None):
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
    attendance = Participation(event=activity, person=authentication.represents(), remark='Enrollment through OAuth',
                               payment_method=Participation.PaymentMethodChoices.NONE, added_by=authentication.represents(),
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


@jsonrpc_method('activityRevokeSignup(Number) -> Boolean', validate=True)
@transaction.atomic
@authentication_required('signup')
def activity_signup_revoke(request, activity_id, authentication=None):
    try:
        # Lockup the Activity object for updating, prevent concurrent (un)enrollments
        activity = Activity.objects.select_for_update().get(id=activity_id)
    except Activity.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if activity.oauth_application and not activity.oauth_application == authentication.get_application():
        raise SignupError("You can only unsubscribe to this activity on the website of this activity.")
    elif not activity.enrollment:
        raise SignupError("You cannot unsubscribe for this activity, it has no subscription.")
    elif not authentication.represents() in activity.participants.all():
        raise SignupError("You were not subscribed for this activity.")
    elif not activity.can_unenroll:
        raise SignupError(
            "You cannot revoke your attendance anymore, it is not possible to unsubscribe for this activity.")
    elif not activity.enrollment_open():
        raise SignupError("You cannot revoke your attendance anymore, subscription term has expired.")

    attendance = Participation.objects.select_for_update().get(person=authentication.represents(), event=activity)

    # If necessary, create a compensation for attendance
    transactions.remove_participation(attendance)

    # Delete attendance
    attendance.delete()

    update_waiting_list(activity=activity)

    return True

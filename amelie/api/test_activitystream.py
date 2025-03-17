from __future__ import division, absolute_import, print_function, unicode_literals

import datetime
from decimal import Decimal

from django.utils import timezone

from amelie.activities.models import Activity, EnrollmentoptionQuestion, EnrollmentoptionCheckbox, EnrollmentoptionFood
from amelie.api.common import strip_markdown
from amelie.personal_tab.models import Authorization, AuthorizationType
from amelie.tools.templatetags import md
from amelie.tools.tests import APITestCase, generate_activities


def _activity_data(activity, signedup=False):
    """
    Generate dict with activity data.
    :param Activity activity: Activity to convert
    :param bool signedup: Value of the signedup field.
    :rtype: dict
    """
    return {
        "id": activity.id,
        "beginDate": activity.begin.isoformat(),
        "endDate": activity.end.isoformat(),
        "title": activity.summary,
        "location": activity.location,
        "category": activity.activity_type,
        "url": activity.get_absolute_url(),
        "organizer": activity.organizer.name,
        'isDutch': activity.dutch_activity,
    }


def _activity_data_detailed(activity, authenticated=False, signedup=False):
    """
    Generate dict with detailed activity data.
    :param Activity activity: Activity to convert
    :rtype: dict
    """
    photoarr = []  # TODO

    options = []
    if authenticated:
        for option in activity.enrollmentoption_set.all():
            if option.content_type.model_class() == EnrollmentoptionQuestion:
                options.append({
                    "question": option.title,
                    "type": "question",
                    "required": option.required,
                    "id": option.id,
                })
            elif option.content_type.model_class() == EnrollmentoptionCheckbox:
                options.append({
                    "question": option.title,
                    "type": "checkbox",
                    "price": option.price_extra,
                    "id": option.id,
                })
            elif option.content_type.model_class() == EnrollmentoptionFood:
                dishes = option.dishprice_set.all()
                choices = []
                for choice in dishes:
                    choices.append({
                        "dish": choice.dish.name,
                        "restaurant": choice.dish.restaurant.name,
                        "id": choice.id,
                        "price": choice.price,
                    })
                options.append({
                    "question": option.title,
                    "type": "selectbox",
                    "id": option.id,
                    "choices": choices,
                    "required": option.required,
                })

    return {
        "id": activity.id,
        "beginDate": activity.begin.isoformat(),
        "endDate": activity.end.isoformat(),
        "title": activity.summary,
        "location": activity.location,
        "category": activity.activity_type,
        "url": activity.get_absolute_url(),
        "organizer": activity.organizer.name,
        "isDutch": activity.dutch_activity,

        "description": strip_markdown(activity.description),
        "html": md.markdown(activity.description),

        "thumbnails": {
            "small": None,
            "medium": None,
            "large": None,
            "original": None
        },
        "images": photoarr,
        "options": options,

        "imageUrl": activity.image_icon.url if activity.image_icon else None,
        "signupRequired": activity.enrollment,
        "availability": activity.maximum if activity.maximum is not None else 0,
        "signupStart": activity.enrollment_begin.isoformat() if activity.enrollment_begin else None,
        "signupStop": activity.enrollment_end.isoformat() if activity.enrollment_end else None,
        "signedUp": signedup,
        "resignAvailable": activity.enrollment and activity.enrollment_open() and activity.can_unenroll,
        "signupAvailable": activity.enrollment and activity.enrollment_open()
                           and not activity.enrollment_full(),
        "signupWaitinglist": activity.enrollment_full(),
        "price": activity.price,
    }


class GetActivityDetailTest(APITestCase):

    def test_non_existent(self):
        """
        Test the getActivityDetailed() call with a non-existent activity.
        """
        self.send_and_compare_request_error('getActivityDetailed', [9001], None, -32095)
        self.send_and_compare_request_error('getActivityDetailed', [9001], self.data['token1'], -32095)

    def test_public(self):
        """
        Test the getActivityDetailed() call with public events.
        """
        generate_activities(10)

        activities = Activity.objects.filter_public(True)
        for activity in activities:
            expected_result = _activity_data_detailed(activity)
            self.send_and_compare_request('getActivityDetailed', [activity.pk], None, expected_result)

        activities = Activity.objects.filter(public=False)
        for activity in activities:
            self.send_and_compare_request_error('getActivityDetailed', [activity.pk], None, -32096)

    def test_private(self):
        """
        Test the getActivityDetailed() call with private events.
        """
        generate_activities(10)

        activities = Activity.objects.filter_public(False)
        for activity in activities:
            expected_result = _activity_data_detailed(activity, authenticated=True)
            self.send_and_compare_request('getActivityDetailed', [activity.pk], self.data['token1'], expected_result)

    def test_invalid_token(self):
        """
        Test the getActivityDetailed() call with private events and an invalid token.
        """
        generate_activities(10)

        activities = Activity.objects.filter(public=False)
        for activity in activities:
            self.send_and_compare_request_error('getActivityDetailed', [activity.pk], 'qNPiKNn3McZIC6fWKE1X', -32096)


class GetActivityStreamTest(APITestCase):

    def test_empty(self):
        """
        Test the getActivityStream() call without contents.
        """
        start = self.isodate_param(timezone.now())
        end = self.isodate_param(timezone.now() + datetime.timedelta(days=31))

        self.send_and_compare_request('getActivityStream', [start, end], None, [])
        self.send_and_compare_request('getActivityStream', [start, end], self.data['token1'], [])

    def test_public(self):
        """
        Test the getActivityStream() call with public events.
        """
        generate_activities(10)

        activities = Activity.objects.filter_public(True)[2:4]
        start = self.isodate_param(activities[0].begin)
        end = self.isodate_param(activities[len(activities)-1].end)
        expected_result = [_activity_data(a) for a in activities]
        self.send_and_compare_request('getActivityStream', [start, end], None, expected_result)

        activities = Activity.objects.filter_public(True)
        start = self.isodate_param(timezone.now())
        end = self.isodate_param(timezone.now() + datetime.timedelta(days=31))
        expected_result = [_activity_data(a) for a in activities]
        self.send_and_compare_request('getActivityStream', [start, end], None, expected_result)

    def test_private(self):
        """
        Test the getActivityStream() call with private events.
        """
        generate_activities(10)

        activities = Activity.objects.filter_public(True)[4:8]
        start = self.isodate_param(activities[0].begin)
        end = self.isodate_param(activities[len(activities)-1].end)
        expected_result = [_activity_data(a) for a in activities]
        self.send_and_compare_request('getActivityStream', [start, end], None, expected_result)

        activities = Activity.objects.filter_public(True)
        start = self.isodate_param(timezone.now())
        end = self.isodate_param(timezone.now() + datetime.timedelta(days=31))
        expected_result = [_activity_data(a) for a in activities]
        self.send_and_compare_request('getActivityStream', [start, end], None, expected_result)

    def test_invalid_token(self):
        """
        Test the getActivityStream() call with an invalid token.
        """
        generate_activities(10)

        start = self.isodate_param(timezone.now())
        end = self.isodate_param(timezone.now() + datetime.timedelta(days=31))
        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(True)]
        self.send_and_compare_request('getActivityStream', [start, end], 'qNPiKNn3McZIC6fWKE1X', expected_result)


class GetUpcomingActivitiesTest(APITestCase):

    def test_empty(self):
        """
        Test the getUpcomingActivities() call without contents.
        """
        self.send_and_compare_request('getUpcomingActivities', [10], None, [])
        self.send_and_compare_request('getUpcomingActivities', [10], self.data['token1'], [])

    def test_public(self):
        """
        Test the getUpcomingActivities() call with public events.
        """
        generate_activities(10)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(True)[:1]]
        self.send_and_compare_request('getUpcomingActivities', [1], None, expected_result)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(True)[:5]]
        self.send_and_compare_request('getUpcomingActivities', [5], None, expected_result)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(True)]
        self.send_and_compare_request('getUpcomingActivities', [10], None, expected_result)

    def test_private(self):
        """
        Test the getUpcomingActivities() call with private events.
        """
        generate_activities(10)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(False)[:1]]
        self.send_and_compare_request('getUpcomingActivities', [1], self.data['token1'], expected_result)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(False)[:5]]
        self.send_and_compare_request('getUpcomingActivities', [5], self.data['token1'], expected_result)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(False)]
        self.send_and_compare_request('getUpcomingActivities', [10], self.data['token1'], expected_result)

    def test_invalid_token(self):
        """
        Test the getUpcomingActivities() call with an invalid token.
        """
        generate_activities(10)

        expected_result = [_activity_data(a) for a in Activity.objects.filter_public(True)]
        self.send_and_compare_request('getUpcomingActivities', [10], 'qNPiKNn3McZIC6fWKE1X', expected_result)


class ActivitySignupTest(APITestCase):

    def setUp(self):
        super(ActivitySignupTest, self).setUp()

        generate_activities(1)
        self.activity = Activity.objects.get()
        self.activity.enrollment = True
        self.activity.enrollment_begin = timezone.now() - datetime.timedelta(hours=1)
        self.activity.enrollment_end = timezone.now() + datetime.timedelta(hours=1)
        self.activity.save()

        auth_type = AuthorizationType(name_nl='Activiteiten', activities=True)
        auth_type.save()
        Authorization(authorization_type=auth_type, person=self.data['person1'], iban="NL13TEST0123456789", bic="TESTNL2A",
                      account_holder_name=self.data['person1'].incomplete_name(), start_date=datetime.date.today(),
                      is_signed=True).save()

    def test_invalid_token(self):
        # Clear options
        for option in self.activity.enrollmentoption_set.all():
            option.delete()

        self.send_and_compare_request_error('activitySignup', [self.activity.pk, 0.00, []], 'invalidToken', -32096)

    def test_free(self):
        # Clear options
        for option in self.activity.enrollmentoption_set.all():
            option.delete()
        # Clear mandate
        Authorization.objects.all().delete()

        self.send_and_compare_request('activitySignup', [self.activity.pk, 0.00, []], self.data['token1'], True)

    def test_no_mandate(self):
        self.activity.price = 12.34
        self.activity.save()
        # Clear options
        for option in self.activity.enrollmentoption_set.all():
            option.delete()
        # Clear mandate
        Authorization.objects.all().delete()

        self.send_and_compare_request_error(
            'activitySignup', [self.activity.pk, 12.34, []], self.data['token1'], -32602
        )

    def test_paid(self):
        self.activity.price = 12.34
        self.activity.save()
        # Clear options
        for option in self.activity.enrollmentoption_set.all():
            option.delete()

        self.send_and_compare_request('activitySignup', [self.activity.pk, 12.34, []], self.data['token1'], True)

    def test_paid_invalid(self):
        self.activity.price = 12.34
        self.activity.save()
        # Clear options
        for option in self.activity.enrollmentoption_set.all():
            option.delete()

        self.send_and_compare_request_error(
            'activitySignup', [self.activity.pk, 12.00, []], self.data['token1'], -32602
        )

    def test_missing_options(self):
        self.send_and_compare_request_error(
            'activitySignup', [self.activity.pk, 0.00, []], self.data['token1'], -32602
        )

    def test_with_options(self):
        self.activity.price = Decimal('12.34')
        self.activity.save()
        price = self.activity.price

        options = []
        for option in EnrollmentoptionQuestion.objects.filter(activity=self.activity):
            options.append({'id': option.pk, 'value': 'text'})
        for option in EnrollmentoptionCheckbox.objects.filter(activity=self.activity):
            options.append({'id': option.pk, 'value': True})
            price += option.price_extra or 0
        for option in EnrollmentoptionFood.objects.filter(activity=self.activity):
            gerecht = option.dishprice_set.all()[0]
            price += gerecht.price
            options.append({'id': option.pk, 'value': gerecht.id})

        self.send_and_compare_request('activitySignup', [self.activity.pk, float(price), options], self.data['token1'],
                                      True)

    def test_mising_option_values(self):
        self.activity.price = Decimal('12.34')
        self.activity.save()
        price = self.activity.price

        options = []
        for option in EnrollmentoptionQuestion.objects.filter(activity=self.activity):
            options.append({'id': option.pk, 'value': ''})
        for option in EnrollmentoptionCheckbox.objects.filter(activity=self.activity):
            options.append({'id': option.pk, 'value': True})
            price += option.price_extra or 0
        for option in EnrollmentoptionFood.objects.filter(activity=self.activity):
            gerecht = option.dishprice_set.all()[0]
            price += gerecht.price
            options.append({'id': option.pk, 'value': gerecht.id})

        self.send_and_compare_request_error(
            'activitySignup', [self.activity.pk, float(price), options], self.data['token1'], -32602
        )

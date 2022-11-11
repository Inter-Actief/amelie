import datetime
import logging
from datetime import timedelta, date

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from oauth2_provider.views import AuthorizedTokenDeleteView

from amelie.activities.models import Activity
from amelie.companies.models import CompanyEvent
from amelie.forms import AmelieAuthenticationForm
from amelie.news.models import NewsItem
from amelie.members.forms import PersonalDetailsEditForm, PersonalStudyEditForm
from amelie.members.models import Person, Committee, StudyPeriod
from amelie.education.models import Complaint, EducationEvent
from amelie.statistics.decorators import track_hits
from amelie.tools.models import Profile
from amelie.videos.models import BaseVideo

logger = logging.getLogger(__name__)


@sensitive_variables('password')
@sensitive_post_parameters('password')
@never_cache
def login(request, template_name='login.html', redirect_field_name=REDIRECT_FIELD_NAME):
    redirect_to = request.POST.get(redirect_field_name, request.GET.get(redirect_field_name, ''))
    if request.method == 'POST':
        form = AmelieAuthenticationForm(data=request.POST)
        if form.is_valid():
            if not url_has_allowed_host_and_scheme(url=redirect_to, allowed_hosts={request.get_host()}):
                redirect_to = settings.LOGIN_REDIRECT_URL
            from django.contrib.auth import login
            login(request, form.get_user())
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            if form.cleaned_data['remain_logged_in']:
                request.session.set_expiry(settings.SESSION_ALTERNATE_EXPIRE)
            return HttpResponseRedirect(redirect_to)

    elif hasattr(request, 'person') and request.person:
        # Prevent redirect loops, redirect to homepage if someone is logged in and goes to /login.
        return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = AmelieAuthenticationForm(request)

    request.session.set_test_cookie()

    # Done
    return render(request, template_name, {
        'form': form,
        'redirect_to': redirect_to,
        'show_oauth': 'no_oauth' not in request.GET,
    })

# The SAML login page throws a very annoying error (UnsolicitedResponse) when a timed-out response arrives, or a bot
# visits our saml url, so we need to wrap it and ignore the error to stop it from showing up in error log mails.
saml_logger = logging.getLogger('djangosaml2')
from djangosaml2.cache import IdentityCache, OutstandingQueriesCache
from djangosaml2.overrides import Saml2Client
from djangosaml2.utils import get_custom_setting, validate_referral_url
from djangosaml2.views import AssertionConsumerServiceView, _set_subject_id
from saml2.response import UnsolicitedResponse, StatusError, StatusAuthnFailed, StatusRequestDenied, \
    StatusNoAuthnContext
from saml2.sigver import SignatureError, MissingKey
from saml2.validate import ToEarly, ResponseLifetimeExceed
from django.contrib import auth
from saml2.saml import SCM_BEARER
from django.http import HttpResponseBadRequest
import saml2
from saml2.s_utils import RequestVersionTooLow
class SAMLACSOverrideView(AssertionConsumerServiceView):

    def post(self, request, attribute_mapping=None, create_unknown_user=None):
        """ SAML Authorization Response endpoint
        """
        if 'SAMLResponse' not in request.POST:
            logger.warning('Missing "SAMLResponse" parameter in POST data.')
            return HttpResponseBadRequest('Missing "SAMLResponse" parameter in POST data.')

        attribute_mapping = attribute_mapping or get_custom_setting(
            'SAML_ATTRIBUTE_MAPPING', {'uid': ('username', )})
        create_unknown_user = create_unknown_user or get_custom_setting(
            'SAML_CREATE_UNKNOWN_USER', True)
        conf = self.get_sp_config(request)

        identity_cache = IdentityCache(request.saml_session)
        client = Saml2Client(conf, identity_cache=identity_cache)
        oq_cache = OutstandingQueriesCache(request.saml_session)
        oq_cache.sync()
        outstanding_queries = oq_cache.outstanding_queries()

        _exception = None
        try:
            response = client.parse_authn_request_response(request.POST['SAMLResponse'],
                                                           saml2.BINDING_HTTP_POST,
                                                           outstanding_queries)
        except (StatusError, ToEarly) as e:
            _exception = e
            logger.exception("Error processing SAML Assertion.")
        except ResponseLifetimeExceed as e:
            _exception = e
            logger.info(
                ("SAML Assertion is no longer valid. Possibly caused "
                 "by network delay or replay attack."), exc_info=True)
        except SignatureError as e:
            _exception = e
            logger.info("Invalid or malformed SAML Assertion.", exc_info=True)
        except StatusAuthnFailed as e:
            _exception = e
            logger.info("Authentication denied for user by IdP.", exc_info=True)
        except StatusRequestDenied as e:
            _exception = e
            logger.warning("Authentication interrupted at IdP.", exc_info=True)
        except StatusNoAuthnContext as e:
            _exception = e
            logger.warning("Missing Authentication Context from IdP.", exc_info=True)
        except MissingKey as e:
            _exception = e
            logger.exception("SAML Identity Provider is not configured correctly: certificate key is missing!")
        except UnsolicitedResponse as e:
            _exception = e
            #logger.exception("Received SAMLResponse when no request has been made.")
        except RequestVersionTooLow as e:
            _exception = e
            logger.exception("Received SAMLResponse have a deprecated SAML2 VERSION.")
        except Exception as e:
            _exception = e
            logger.exception("SAMLResponse Error")

        if _exception:
            return self.handle_acs_failure(request, exception=_exception)
        elif response is None:
            logger.warning("Invalid SAML Assertion received (unknown error).")
            return self.handle_acs_failure(request, status=400, exception=SuspiciousOperation('Unknown SAML2 error'))

        try:
            self.custom_validation(response)
        except Exception as e:
            logger.warning(f"SAML Response validation error: {e}")
            return self.handle_acs_failure(request, status=400, exception=SuspiciousOperation('SAML2 validation error'))

        session_id = response.session_id()
        oq_cache.delete(session_id)

        # authenticate the remote user
        session_info = response.session_info()

        # assertion_info
        assertion = response.assertion
        assertion_info = {}
        for sc in assertion.subject.subject_confirmation:
            if sc.method == SCM_BEARER:
                assertion_not_on_or_after = sc.subject_confirmation_data.not_on_or_after
                assertion_info = {'assertion_id': assertion.id,
                                  'not_on_or_after': assertion_not_on_or_after}
                break

        if callable(attribute_mapping):
            attribute_mapping = attribute_mapping()
        if callable(create_unknown_user):
            create_unknown_user = create_unknown_user()

        logger.debug(
            'Trying to authenticate the user. Session info: %s', session_info)
        user = auth.authenticate(request=request,
                                 session_info=session_info,
                                 attribute_mapping=attribute_mapping,
                                 create_unknown_user=create_unknown_user,
                                 assertion_info=assertion_info)
        if user is None:
            logger.warning(
                "Could not authenticate user received in SAML Assertion. Session info: %s", session_info)
            return self.handle_acs_failure(request, exception=PermissionDenied('No user could be authenticated.'),
                                           session_info=session_info)

        auth.login(self.request, user)
        _set_subject_id(request.saml_session, session_info['name_id'])
        logger.debug("User %s authenticated via SSO.", user)

        self.post_login_hook(request, user, session_info)
        self.customize_session(user, session_info)

        relay_state = self.build_relay_state()
        custom_redirect_url = self.custom_redirect(
            user, relay_state, session_info)
        if custom_redirect_url:
            return HttpResponseRedirect(custom_redirect_url)
        relay_state = validate_referral_url(request, relay_state)
        logger.debug('Redirecting to the RelayState: %s', relay_state)
        return HttpResponseRedirect(relay_state)


@login_required
def profile_edit(request):
    if not hasattr(request, 'person'):
        return render(request, "profile_unknown.html", {})

    study_period = None
    study = None
    begin = None
    study_form = PersonalStudyEditForm()
    profile = Profile.objects.filter(user=request.user).first()

    if hasattr(request.person, 'student'):
        try:
            study_period = request.person.student.studyperiod_set.get(
                begin__lte=timezone.now() - timedelta(days=365*3),
                end__isnull=True,
                study__type='BSc',
                study__primary_study=True
            )
            study = study_period.study
            begin = study_period.begin
        except StudyPeriod.DoesNotExist:
            pass
        except StudyPeriod.MultipleObjectsReturned:
            pass

    if request.method == "POST":
        form = PersonalDetailsEditForm(request.POST, instance=request.person)

        if form.is_valid():
            try:
                profile = Profile.objects.get(user=request.user)
            except Profile.DoesNotExist:
                profile = Profile(user=request.user)

            if study_period:
                study_form = PersonalStudyEditForm(request.POST)

                if study_form.is_valid():
                    study_form.save(study_period=study_period)

            profile.save()
            form.save()

            return redirect('profile_overview')
    else:
        form = PersonalDetailsEditForm(instance=request.person)

    return render(request, "profile_edit.html", {
        'study': study,
        'begin': begin,
        'study_form': study_form,
        'profile': profile,
        'form': form
    })


@login_required
def profile_overview(request):
    return render(request, "profile_overview.html")


@track_hits("Frontpage")
def frontpage(request):
    activity_list_length = 10
    now = timezone.now()

    # Logged in users need to have a profile
    if request.user.is_authenticated and not Profile.objects.filter(user=request.user).exists():
        # No profile yet, so redirect to profile editor to have them check their details
        return redirect('profile_edit')

    current_activities = list(Activity.objects.filter_public(request)
                              .filter(begin__lte=now, end__gt=now))
    current_activities += list(CompanyEvent.objects.filter(visible_from__lte=now, visible_till__gt=now)
                               .filter(begin__lte=now, end__gt=now))
    current_activities += list(EducationEvent.objects.filter_public(request)
                                                     .filter(begin__lte=now, end__gt=now))

    # Cut the list to the maximum and let python sort the list instead of django,
    # since there are multiple model types in the list.
    current_activities = sorted(current_activities[:activity_list_length], key=lambda a: a.begin)

    # Upcoming activities
    upcoming_activities = list(Activity.objects.filter_public(request)
                               .filter(begin__gt=now))
    upcoming_activities += list(CompanyEvent.objects.filter(visible_from__lte=now, visible_till__gt=now)
                                .filter(begin__gt=now))
    upcoming_activities += list(EducationEvent.objects.filter_public(request)
                                .filter(begin__gt=now))

    upcoming_activities = sorted(upcoming_activities,
                                 key=lambda a: a.begin)[:activity_list_length - len(current_activities)]

    # Picture reel
    if hasattr(request, 'person'):
        # Logged in, show all pictures
        past_activities = Activity.objects.distinct().filter(begin__lt=timezone.now(),
                                                             photos__gt=0).order_by('-begin')[:3]
    else:
        # Only show public pictures
        past_activities = Activity.objects.distinct().filter(begin__lt=timezone.now(),
                                                             photos__gt=0,
                                                             photos__public=True).order_by('-begin')[:3]

    # Featured video
    featured_video = BaseVideo.objects.filter_public(request).filter(is_featured=True).first()

    # News
    education_committee = Committee.education_committee()
    news = NewsItem.objects.select_related('author', 'publisher').order_by('-pinned', '-publication_date')
    if education_committee:
        education_news = news.filter(publisher=education_committee)[:3]
        news = news.exclude(publisher=education_committee)
    else:
        education_news = news.none()
    news = news[:3]

    context = {
        'current_activities': current_activities,
        'upcoming_activities': upcoming_activities,
        'past_activities': past_activities,
        'featured_video': featured_video,
        'streaming_base_url': settings.STREAMING_BASE_URL,
        'news': news,
        'education_news': education_news,
    }

    if request.user.is_authenticated:
        # MediaCie check
        context['mediacie'] = request.person.function_set.filter(committee__abbreviation='MediaCie',
                                                                 end__isnull=True).exists()

        # Birthdays
        context['birthdays'] = Person.objects.members().filter(date_of_birth__day=date.today().day,
                                                               date_of_birth__month=date.today().month).distinct()

        # Complaints
        if request.is_board:
            complaints = Complaint.objects.filter(completed=False)
        else:
            complaints = Complaint.objects.filter(Q(completed=False) & (Q(public=True) | Q(reporter=request.person)))
        context['complaints'] = complaints.select_related('course').order_by('-published')[:5]

    return render(request, "frontpage.html", context)


def server_error(request, template_name='500.html'):
    return render(request, template_name, status=500)


def csrf_failure(request, reason=""):
    logger.warning('CSRF-check failed. Reason: %s' % reason, extra={'request': request})

    if reason and settings.DEBUG:
        reason = _('CSRF-check failed. Reason: %s' % reason)
    else:
        reason = _('CSRF-check failed.')

    return render(request, "403.html", {'reason': reason}, status=403)


class AuthorizedTokenDeleteViewAmelieWrapper(AuthorizedTokenDeleteView):
    success_url = reverse_lazy('profile_overview')


def security_txt(request):
    month_from_now = datetime.datetime.now() + datetime.timedelta(weeks=4)
    content = f"""# Our security address(es), in order of preference
Contact: mailto:vulnerabilities@inter-actief.net
Contact: mailto:www-super@inter-actief.net
Contact: {settings.ABSOLUTE_PATH_TO_SITE}/about/7/contact/
Contact: tel:+3153-489-3756

# Where this file can be found
Canonical: {settings.ABSOLUTE_PATH_TO_SITE}/.well-known/security.txt

# Link to our full Coordinated Vulnerability Disclosure policy
Policy: {settings.ABSOLUTE_PATH_TO_SITE}/about/33/coordinated-vulnerability-disclosure-policy/

Preferred-Languages: en, nl

Expires: {month_from_now:%Y-%m-%dT%H:%M:%Sz%z}"""
    return HttpResponse(content, content_type="text/plain")

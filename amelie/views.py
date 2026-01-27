import datetime
import logging
import os
from datetime import timedelta, date

import requests
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.core.exceptions import BadRequest
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from health_check.views import MainView as HealthCheckMainView
from oauth2_provider.views import AuthorizedTokenDeleteView

from amelie.activities.models import Activity
from amelie.companies.models import CompanyEvent
from amelie.forms import AmelieAuthenticationForm
from amelie.members.forms import ProfilePictureUploadForm, ProfilePictureVerificationForm
from amelie.news.models import NewsItem
from amelie.members.forms import PersonalDetailsEditForm, PersonalStudyEditForm
from amelie.members.models import Person, Committee, StudyPeriod
from amelie.education.models import Complaint, EducationEvent
from amelie.statistics.decorators import track_hits
from amelie.tools.auth import get_user_info, unlink_totp, unlink_acount, unlink_passkey, register_totp, register_passkey
from amelie.tools.mixins import RequirePersonMixin, RequireSuperuserMixin, RequireBoardMixin, RequireActiveMemberMixin
from amelie.tools.buildinfo import get_build_info
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


def get_oidc_logout_url(request):
    # After logout, we need to redirect to the OIDC Single Sign Out
    # endpoint (OIDC_LOGOUT_URL) with a redirect back to the main page
    params = urlencode({
        'id_token_hint': request.session.get("oidc_id_token", ""),
        'post_logout_redirect_uri': request.build_absolute_uri(reverse("frontpage"))
    })
    return f"{settings.OIDC_LOGOUT_URL}?{params}"


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
    # Retrieve the person's other accounts from Keycloak
    try:
        users = get_user_info(request.user.person)

        # Extract user credentials of type TOTP and Webauthn-Passwordless into separate lists for rendering in template
        for user in users:
            user['credentialsTOTP'] = []
            user['credentialsPasskey'] = []
            for credential in user['credentials']:
                if credential['type'] == "otp":
                    user['credentialsTOTP'].append(credential)
                if credential['type'] == "webauthn-passwordless":
                    user['credentialsPasskey'].append(credential)

    except Exception as e:
        logger.exception(e)
        users = []

    # Retrieve SSH keys from Kanidm, via the person's claudia mapping.
    try:
        ssh_keys = []
        from amelie.claudia.models import Mapping
        mp = Mapping.find(request.user.person)
        kanidm_person = None
        if mp and mp.get_kanidm_id():
            from amelie.claudia.kanidm import KanidmAPI
            kanidm_api = KanidmAPI()
            kanidm_person = kanidm_api.get_person(mp.get_kanidm_id())
        if kanidm_person:
           ssh_keys = kanidm_person.list_ssh_pubkeys()
    except Exception as e:
        logger.exception(e)
        ssh_keys = []

    return render(request, "profile_overview.html", context={
        'users': users,
        'ssh_keys': ssh_keys,
        'providers_unlink_allowed': settings.KEYCLOAK_PROVIDERS_UNLINK_ALLOWED
    })


@login_required
def profile_actions(request, action, user_id, arg):
    users = get_user_info(request.user.person)
    if user_id not in [x['id'] for x in users]:
        raise PermissionError("You are not associated with this user.")
    if action == "unlink_totp":
        if user_id and arg:
            unlink_totp(user_id, arg)
    elif action == "unlink_social":
        if user_id and arg:
            unlink_acount(user_id, arg)
    elif action == "unlink_passkey":
        if user_id and arg:
            unlink_passkey(user_id, arg)
    elif action == "register_totp":
        if user_id:
            register_totp(user_id)
    elif action == "register_passkey":
        if user_id:
            register_passkey(user_id)
    else:
        raise BadRequest("Unknown action.")

    return redirect("profile_overview")


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
        'peertube_base_url': settings.PEERTUBE_BASE_URL,
        'news': news,
        'education_news': education_news,
    }

    if request.user.is_authenticated:
        # MediaCie check
        context['mediacie'] = request.person.is_in_committee('MediaCie')

        # Room Duty check
        context['is_roomduty'] = request.person.is_room_duty()

        # Birthdays
        context['birthdays'] = Person.objects.members().filter(
            date_of_birth__day=date.today().day,
            date_of_birth__month=date.today().month,
            preferences__name="birthday_show_frontpage",
        ).distinct()

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
        reason = _l('CSRF-check failed. Reason: %s' % reason)
    else:
        reason = _l('CSRF-check failed.')

    return render(request, "403.html", {'reason': reason}, status=403)


class AuthorizedTokenDeleteViewAmelieWrapper(AuthorizedTokenDeleteView):
    success_url = reverse_lazy('profile_overview')


def robots_txt(request):
    # Return the robots.txt of the configured environment, or PRODUCTION if no specific one exists.
    path = os.path.join(settings.BASE_PATH, f'amelie/style/robots.{settings.ENV}.txt')
    if not os.path.isfile(path):
        path = os.path.join(settings.BASE_PATH, "amelie/style/robots.PRODUCTION.txt")

    with open(path, 'r') as f:
        return HttpResponse(f.read(), content_type='text/plain')


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


def healthz_view(request):
    return HttpResponse('ok', content_type="text/plain")


class PortraitUploadVerification(RequireBoardMixin, FormView):
    http_method_names = ["get", "post"]
    form_class = ProfilePictureVerificationForm

    def get(self, request, *args, **kwargs):
        people = Person.objects.filter(unverified_picture__isnull=False).exclude(unverified_picture='')[:50]
        forms = [(ProfilePictureVerificationForm(initial={'id':person.id}), person) for person in people]

        return render(request, 'profile_picture_verification.html', locals())

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            person = Person.objects.filter(id=form.data.get("id")).first()

            if person is None:
                return "error"

            if form.data.get("is_verified") == "true":
                person.picture = person.unverified_picture
                person.unverified_picture = None
                person.save()
            else:
                os.remove(person.unverified_picture.path)
                person.unverified_picture = None
                person.save()
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "error"})


class PortraitUploadView(RequirePersonMixin, FormView):
    http_method_names = ["get", "post"]
    form_class = ProfilePictureUploadForm

    def get(self, request, *args, **kwargs):
        form = ProfilePictureUploadForm()
        return render(request, 'profile_portrait_upload.html', locals())

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = form.files.getlist("profile_picture")

        if form.is_valid():
            if len(files) == 0:
                return self.form_invalid(form)
            request.person.is_portrait_picture_verified = False
            request.person.unverified_picture = files[0]
            request.person.save()
        else:
            return self.form_invalid(form)

        return redirect('profile_overview')


def _get_queue_information():
    # Celery worker information
    if settings.FLOWER_URL:
        try:
            celery_workers = []
            worker_data = requests.get(f"{settings.FLOWER_URL}/workers?json=1").json()
            for worker in worker_data.get('data', []):

                last_heartbeat = None
                for heartbeat in worker.get('heartbeats', []):
                    try:
                        heartbeat_dt = datetime.datetime.fromtimestamp(heartbeat)
                        if last_heartbeat is None or heartbeat_dt > last_heartbeat:
                            last_heartbeat = heartbeat_dt
                    except ValueError:
                        pass

                celery_workers.append({
                    'name': worker.get("hostname", None),
                    'status': worker.get("status", False),
                    'active': worker.get("active", 0),
                    'processed': worker.get("task-received", 0),
                    'failed': worker.get("task-failed", 0),
                    'succeeded': worker.get("task-succeeded", 0),
                    'retried': worker.get("task-retried", 0),
                    'loadavg': worker.get("loadavg", []),
                    'last_heartbeat': last_heartbeat,
                })
            celery_workers = sorted(celery_workers, key=lambda w: w['name'])
        except Exception as e:
            logger.exception(e)
            celery_workers = []
    else:
        celery_workers = []

    # RabbitMQ Queue information
    if settings.RABBITMQ_MGMT_API_URL:
        try:
            if settings.RABBITMQ_MGMT_VHOST:
                vhost_name = settings.RABBITMQ_MGMT_VHOST
            else:
                vhost_name = "amelie"
            if settings.CELERY_TASK_QUEUES:
                queue_names = [q.name for q in settings.CELERY_TASK_QUEUES]
            else:
                # Assume default names
                queue_names = ["default", "mail", "claudia"]
            rabbitmq_queues = []
            for queue in queue_names:
                # Query RabbitMQ API
                data = requests.get(f"{settings.RABBITMQ_MGMT_API_URL}/queues/{vhost_name}/{queue}").json()
                rabbitmq_queues.append({
                    'name': data.get('name', None),
                    'vhost': data.get('vhost', None),
                    'state': data.get('state', None),
                    'consumers': data.get('consumers', 0),
                    'messages': {
                        'current_queued': data.get('messages', 0),
                        'total_incoming': data.get('message_stats', {}).get('publish', 0),
                        'total_delivered': data.get('message_stats', {}).get('deliver_get', 0),
                        'incoming_rate': data.get('message_stats', {}).get('publish_details', {}).get('rate', 0.0),
                        'delivered_rate': data.get('message_stats', {}).get('deliver_get_details', {}).get('rate', 0.0),
                    }
                })
            rabbitmq_queues = sorted(rabbitmq_queues, key=lambda q: q['name'])
        except Exception as e:
            logger.exception(e)
            rabbitmq_queues = []
    else:
        rabbitmq_queues = []

    return {
        'celery': celery_workers,
        'rabbitmq': rabbitmq_queues,
    }


class SystemInfoView(RequireSuperuserMixin, HealthCheckMainView):
    def get_context_data(self, **kwargs):
        import os, sys, platform, socket

        # Operating system version
        if hasattr(platform, 'dist') and platform.dist()[0] != '' and platform.dist()[1] != '':
            os_version = f'{platform.system()} {platform.release()} ({platform.dist()[0].capitalize()} {platform.dist()[1]})'
        else:
            os_version = f'{platform.system()} {platform.release()}'

        # IP address of host
        try:
            ip_address = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip_address = None

        # Process ID of worker
        try:
            process_id = f'{os.getpid()} (parent: {os.getppid()})' if hasattr(os, 'getpid') and hasattr(os, 'getppid') else None
        except Exception:
            process_id = None

        # Build information
        build_info = get_build_info()

        # Celery and RabbitMQ task queue information
        queue_info = _get_queue_information()

        # Build context dict
        context = super().get_context_data(**kwargs)
        # Celery worker info
        context['celery_workers'] = queue_info.get('celery', [])
        # RabbitMQ queue info
        context['rabbitmq_queues'] = queue_info.get('rabbitmq', [])
        # A bunch of other random system information
        context['info_tables'] = [
            ('Amelie', {
                'Build branch': build_info.get("branch", "unknown"),
                'Build commit': build_info.get("commit", "unknown"),
                'Build date': build_info.get("date", "unknown"),
            }),
            ('System', {
                'Python Version': platform.python_version(),
                'Python Subversion': ', '.join(sys.subversion) if hasattr(sys, 'subversion') else None,
                'OS Version': os_version,
                'Executable': sys.executable if hasattr(sys, 'executable') else None,
                'Build Date': platform.python_build()[1],
                'Compiler': platform.python_compiler(),
                'API Version': sys.api_version if hasattr(sys, 'api_version') else None
            }),
            ('Networking', {
                'Hostname': socket.gethostname(),
                'Hostname (fully qualified)': socket.gethostbyaddr(socket.gethostname())[0],
                'IP Address': ip_address,
                'IPv6 Support': getattr(socket, 'has_ipv6', False),
                'SSL Support': hasattr(socket, 'ssl'),
            }),
            ('Python Internals', {
                'Built-in Modules': ', '.join(sys.builtin_module_names) if hasattr(sys, 'builtin_module_names') else None,
                'Byte Order': f'{sys.byteorder} endian',
                'Check Interval': sys.getcheckinterval() if hasattr(sys, 'getcheckinterval') else None,
                'File System Encoding': sys.getfilesystemencoding() if hasattr(sys, 'getfilesystemencoding') else None,
                'Maximum Recursion Depth': sys.getrecursionlimit() if hasattr(sys, 'getrecursionlimit') else None,
                'Maximum Traceback Limit': sys.tracebacklimit if hasattr(sys, 'tracebacklimit') else '1000',
                'Maximum Unicode Code Point': sys.maxunicode
            }),
            ('OS Internals', {
                'Current Working Directory': os.getcwd() if hasattr(os, 'getcwd') else None,
                'Effective Group ID': os.getegid() if hasattr(os, 'getegid') else None,
                'Effective User ID': os.geteuid() if hasattr(os, 'geteuid') else None,
                'Group ID': os.getgid() if hasattr(os, 'getgid') else None,
                'Group Membership': ', '.join(map(str, os.getgroups())) if hasattr(os, 'getgroups') else None,
                'Line Seperator': repr(os.linesep)[1:-1] if hasattr(os, 'linesep') else None,
                'Load Average': ', '.join(map(str, map(lambda x: round(x, 2), os.getloadavg()))) if hasattr(os, 'getloadavg') else None,
                'Path Seperator': os.pathsep if hasattr(os, 'pathsep') else None,
                'Process ID': process_id,
                'User ID': os.getuid() if hasattr(os, 'getuid') else None,
            })
        ]
        return context


class CeleryInfoPartialView(RequireSuperuserMixin, TemplateView):
    template_name = 'health_check/partial_celery_tables.html'

    def get_context_data(self, **kwargs):
        # Celery and RabbitMQ task queue information
        queue_info = _get_queue_information()

        return {
            **super().get_context_data(**kwargs),
            # Celery worker info
            'celery_workers': queue_info.get('celery', []),
            # RabbitMQ queue info
            'rabbitmq_queues': queue_info.get('rabbitmq', []),
        }

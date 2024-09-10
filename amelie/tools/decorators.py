from functools import wraps

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.shortcuts import render
from urllib.parse import quote
from django.utils.translation import gettext_lazy as _l

from amelie.api.utils import has_valid_oauth_token


def request_passes_test(test, needs_login=False, needs_oauth_login=False, reden=''):
    """
    :param test: A function that needs to return True to be able to access the page.
    :param needs_login: If the user needs to be explicitly logged into the website.
    :param needs_oauth_login: If the user needs to be logged in either through the website or with an oAuth token.
    :param reden: Reason to show to the user if they do not have access to the page.
    """
    def _check_request(view_func):
        @wraps(view_func)
        def _do_test_request(request, *args, **kwargs):
            url = '%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, quote(request.get_full_path()))

            if needs_login and not hasattr(request, 'person'):
                return HttpResponseRedirect(url)
            elif needs_oauth_login and not (hasattr(request, 'person') or has_valid_oauth_token(request)):
                return HttpResponseRedirect(url)
            else:
                if not test(request):
                    return render(request, "403.html", {'reden': reden}, status=403)
                else:
                    return view_func(request, *args, **kwargs)

        return _do_test_request

    return _check_request


def require_ajax(func):
    return request_passes_test(lambda r: r.headers.get('x-requested-with') == 'XMLHttpRequest',
                               reden=_l('AJAX request required'))(func)


def require_board(func):
    return request_passes_test(lambda r: hasattr(r, 'is_board') and r.is_board,
                               needs_login=True,
                               reden=_l('Access for board members only.'))(func)


def require_education(func):
    return request_passes_test(lambda r: hasattr(r, 'is_education_committee') and r.is_education_committee,
                               needs_login=True,
                               reden=_l('Access for the Educational Committee only.'))(func)


def require_lid(func):
    return request_passes_test(lambda r: (hasattr(r, 'person') and r.person.is_member()),
                               needs_login=True,
                               reden=_l('For active members only.'))(func)


def require_lid_or_oauth(func):
    return request_passes_test(lambda r: ((hasattr(r, 'person') and r.person.is_member()) or has_valid_oauth_token(r)),
                               needs_oauth_login=True,
                               reden=_l('For active members only.'))(func)


def require_actief(func):
    return request_passes_test(lambda r: (hasattr(r, 'person') and r.person.is_active_member()),
                               needs_login=True,
                               reden=_l('Access for active members only.'))(func)


def require_superuser(func):
    return request_passes_test(lambda r: r.user.is_superuser, needs_login=True,
                               reden=_l('Only accessible by superusers.'))(func)


def require_committee(abbreviation):
    """
    Require a committee using its abbreviation
    """

    def _view(func):
        return request_passes_test(lambda r: (hasattr(r, 'person') and
                                              (r.is_board or r.person.function_set.filter(
                                                  committee__abbreviation=abbreviation, end__isnull=True))),
                                   needs_login=True,
                                   reden=_l('Access for members of the committee only.'))(func)

    return _view

def require_room_duty():
    return require_committee(settings.ROOM_DUTY_ABBREVIATION)

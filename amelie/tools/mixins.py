"""
This module contains mixins for Django class-based views handling authorization tests.
"""
import logging

from abc import abstractmethod

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.shortcuts import render
from urllib.parse import quote
from django.utils.translation import gettext_lazy as _l

from amelie.members.models import Committee, DogroupGeneration
from amelie.tools.logic import current_association_year
from amelie.tools.http import get_client_ips


class PassesTestMixin(object):
    """
    Mixin for validating a access requirement for a view.
    """
    needs_login = False
    """ Indicates if a current login is required for accessing this page. """
    reason = ''
    """ The reason to be returned when the requirement for accessing this page is failed. """

    @abstractmethod
    def test_requirement(self, request):
        """
        Test the requirement for accessing this page.
        This function should return True if accessing this page is allowed.
        """
        return True

    def dispatch(self, request, *args, **kwargs):
        url = '%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, quote(request.get_full_path()))
        if self.needs_login and not hasattr(request, 'person'):
            return HttpResponseRedirect(url)
        else:
            if not self.test_requirement(request):
                return render(request, "403.html", {'reason': self.reason}, status=403)
            else:
                return super(PassesTestMixin, self).dispatch(request, *args, **kwargs)


class RequirePersonMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Access for (former) members only.')

    def test_requirement(self, request):
        return hasattr(request, 'person') and request.person


class RequireBoardMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Access for boardmembers only.')

    def test_requirement(self, request):
        return hasattr(request, 'is_board') and request.is_board


class RequireEducationCommitteeMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Access for the Educational Committee only.')

    def test_requirement(self, request):
        return hasattr(request, 'is_education_committee') and request.is_education_committee


class RequireMemberMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Only for members with an active membership.')

    def test_requirement(self, request):
        return hasattr(request, 'person') and request.person.is_member()


class RequireActiveMemberMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Access for active members only.')

    def test_requirement(self, request):
        return hasattr(request, 'person') and request.person.is_active_member()


class RequireSuperuserMixin(PassesTestMixin):
    needs_login = True
    reason = _l('Only accessible by superusers.')

    def test_requirement(self, request):
        return request.user.is_superuser


class RequireCommitteeMixin(PassesTestMixin):
    """
    Require a committee based on an abbreviation
    """
    needs_login = True
    reason = _l('Access for members of the committee only.')
    abbreviation = None
    """ Abbreviation of the committee required for accessing this page. """

    def test_requirement(self, request):
        return (
            hasattr(request, 'person') and
            (request.is_board or request.person.is_in_committee(self.abbreviation))
        )


class RequireStrictCommitteeMixin(PassesTestMixin):
    """
    Require a committee based on an abbreviation, board not included.
    """
    needs_login = True
    reason = _l('Access for members of the committee only.')
    abbreviation = None
    """ Abbreviation of the committee required for accessing this page. """

    def test_requirement(self, request):
        return (
            hasattr(request, 'person') and
            (request.user.is_superuser or request.person.is_in_committee(self.abbreviation))
        )


class RequireCommitteeOrChildCommitteeMixin(PassesTestMixin):
    """
    Require a committee or child committees of that committee based on an abbreviation
    """
    needs_login = True
    reason = _l('Access for members of the committee only.')
    abbreviation = None
    """ Abbreviation of the (parent) committee required for accessing this page. """

    def test_requirement(self, request):

        if not hasattr(request, 'person'):
            return False

        if hasattr(request, 'is_board') and request.is_board:
            return True

        try:
            parent_committee = Committee.objects.get(abbreviation=self.abbreviation, abolished__isnull=True)
            committees = [parent_committee]
            for child_committee in parent_committee.committee_set.filter(abolished__isnull=True):
                committees.append(child_committee)
        except Committee.DoesNotExist:
            return False

        return request.person.function_set.filter(committee__in=committees, end__isnull=True)


class RequireDoGroupParentInCurrentYearMixin(PassesTestMixin):
    """
    Require that the person is a do group parent in this year
    """
    needs_login = True
    reason = _l('Access for do-group parents only.')

    def test_requirement(self, request):
        if not hasattr(request, 'person'):
            return False

        if hasattr(request, 'is_board') and request.is_board:
            return True

        parents = []
        dogroups = DogroupGeneration.objects.filter(generation=current_association_year())
        for dogroup in dogroups:
            parents.extend(dogroup.parents.all())

        return request.person in parents


class RequireCookieCornerMixin(PassesTestMixin):
    """
    Require that the request be made from the cookie corner computer (or by a logged-in superuser)
    """
    needs_login = False
    reason = _l("Access for the cookie-corner computer only.")

    def test_requirement(self, request):
        if settings.DEBUG or request.user.is_superuser:
            return True
        else:
            all_ips, real_ip = get_client_ips(request)
            access_allowed = real_ip in settings.COOKIE_CORNER_POS_IP_ALLOWLIST or request.user.is_superuser
            if not access_allowed:
                logger = logging.getLogger("amelie.tools.mixins.RequireCookieCornerMixin.test_requirement")
                logger.warning(f"Client with IP '{real_ip}' was denied access to cookie corner. Not on allowlist. Possible (unchecked) other IPs: {all_ips}")
            return access_allowed

class DeleteMessageMixin(object):
    """
    Adds a delete message on successful object deletion.

    Based on https://code.djangoproject.com/attachment/ticket/21936/0001-Add-deletemessagemixin.patch
    """
    delete_message = ''

    def get_delete_message(self):
        return self.delete_message % {'object': self.get_object()}

    def delete(self, request, *args, **kwargs):
        delete_message = self.get_delete_message()
        result = super(DeleteMessageMixin, self).delete(request, *args, **kwargs)
        if delete_message:
            messages.success(request, delete_message)
        return result

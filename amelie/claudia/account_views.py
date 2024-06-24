from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _l
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

from amelie.claudia.forms import AccountPasswordForm, AccountConfigureForwardingForm, AccountPasswordResetForm, \
    AccountPasswordResetLinkForm, AccountActivateForm, MailAliasForm
from amelie.claudia.google import GoogleSuiteAPI
from amelie.claudia.models import Mapping, Membership, AliasGroup
from amelie.claudia.tasks import verify_mapping
from amelie.members.models import Person
from amelie.tools.http import HttpJSONResponse
from amelie.tools.mixins import RequireActiveMemberMixin, RequirePersonMixin


##
# Helper functions
##
def _get_ad():
    """
    Gets a connected AD object
    """
    from amelie.claudia.ad import AD
    a = settings.CLAUDIA_AD
    return AD(a["LDAP"], a["HOST"], a["USER"], a["PASSWORD"], a["BASEDN"], a["PORT"])


def _valid_password(account_name, password):
    """
    Checks a username and password.

    This function checks if the username exists and if the username and the password are correct.

    Returns a tuple with two values:
    - True or False: True if the username/password combination is valid
    - Reason why the combination was rejected (None if it was valid)
    """
    import ldap
    from amelie.claudia.ad import AD

    ad = _get_ad()

    person = ad.find_person(account_name)
    if not person:
        return False, _l('Enter a correct username and password. Warning: the fields are case-sensitive.')
    else:
        # Check if the user needs to change their password
        change_back = not person.has_changed_password()
        if change_back:
            person.must_not_change_password()
        try:
            # Try to connect with given username and password
            a = settings.CLAUDIA_AD
            ad2 = AD(a["LDAP"], a["HOST"], account_name, password, a["BASEDN"], a["PORT"])
            ad2.find_person(account_name)
            return True, None
        except ldap.INVALID_CREDENTIALS:
            return False, _l('Enter a correct username and password. Warning: the fields are case-sensitive.')
        except ldap.OPERATIONS_ERROR:
            return False, _l('Something went wrong, please contact the system administrators.')
        finally:
            if change_back:  # Don't forget the checkbox
                person.must_change_password()


def _process_password(account_name, current_password, new_password):
    """
    Process the password change.

    Returns a tuple with two values:
    - True or False: True if the change was successful
    - Reason why the change failed (None if it was successful)
    """
    res, error = _valid_password(account_name, current_password)
    if res:
        return _process_set_password(account_name, new_password)
    else:
        return res, error


def _process_set_password(account_name, new_password):
    import ldap

    try:
        ad = _get_ad()
        person = ad.find_person(account_name)
        person.set_password(new_password)
        return True, None
    except ldap.INSUFFICIENT_ACCESS:
        return False, _l('Something went wrong, please contact the system administrators.')


def _process_activate(account_name, current_password, new_password):
    """
    Process the activation of the account.

    Returns a tuple with two values:
    - True or False: True if the activation was successful
    - Reason why the activation failed (None if it was successful)
    """
    res, error = _valid_password(account_name, current_password)
    if res:
        import ldap

        try:
            ad = _get_ad()
            person = ad.find_person(account_name)
            if person.has_changed_password():
                return False, _l('Your account has already been activated.')
            else:
                person.set_password(new_password)
                return True, None
        except ldap.INSUFFICIENT_ACCESS:
            return False, _l('Something went wrong, please contact the system administrators.')
        except ldap.INVALID_CREDENTIALS:
            return False, _l('It looks like you have entered an unknown username and password combination. '
                            'Please contact the administrators if you are sure you entered a correct combination.')

    else:
        return res, error


##
# Account views
##
class AccountHome(TemplateView):
    """
    Index page for account pages
    """
    template_name = 'accounts/home.html'


class AccountError(TemplateView):
    """
    Error page for accounts
    """
    template_name = 'accounts/error.html'

    error = _l("Something went wrong, please contact the system administrators.")

    def get_context_data(self, **kwargs):
        context = super(AccountError, self).get_context_data()
        if 'error' in kwargs.keys():
            self.error = kwargs['error']
        context['error'] = self.error
        return context

    def post(self, *args, **kwargs):
        return self.get(self, *args, **kwargs)


@method_decorator(sensitive_post_parameters('current_password', 'new_password', 'new_password2'), name='dispatch')
class AccountActivate(FormView):
    """
    Page to activate an Inter-Actief account
    """
    template_name = 'accounts/activate.html'
    form_class = AccountActivateForm
    success_url = reverse_lazy('account:activate_success')

    def form_valid(self, form):
        account_name = form.cleaned_data['account_name']
        current_password = form.cleaned_data['current_password']
        new_password = form.cleaned_data['new_password']

        res, error = _process_activate(account_name, current_password, new_password)

        if error:
            self.response_class = AccountError.as_view(error=error)
            return self.render_to_response({})

        return super(AccountActivate, self).form_valid(form)


class AccountActivateSuccess(TemplateView):
    """
    Page to show the activation success message
    """
    template_name = 'accounts/activate_success.html'


@method_decorator(sensitive_post_parameters('current_password', 'new_password', 'new_password2'), name='dispatch')
class AccountPassword(RequireActiveMemberMixin, FormView):
    """
    Page to change the password of an Inter-Actief account
    """
    template_name = 'accounts/password.html'
    form_class = AccountPasswordForm
    success_url = reverse_lazy('account:password_success')

    def form_valid(self, form):
        account_name = self.request.user.person.account_name
        current_password = form.cleaned_data['current_password']
        new_password = form.cleaned_data['new_password']

        res, error = _process_password(account_name, current_password, new_password)

        if error:
            return AccountError.as_view(error=error)

        return super(AccountPassword, self).form_valid(form)


class AccountPasswordSuccess(RequireActiveMemberMixin, TemplateView):
    """
    Page to show the password change success message
    """
    template_name = 'accounts/password_success.html'


class AccountPasswordReset(FormView):
    """
    Page to reset a user's password with
    """
    template_name = 'accounts/password_reset.html'
    form_class = AccountPasswordResetForm
    success_url = reverse_lazy('account:password_reset_success')

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect("account:password")
        return super(AccountPasswordReset, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.send_email()
        return super(AccountPasswordReset, self).form_valid(form)


class AccountPasswordResetSuccess(TemplateView):
    template_name = "accounts/password_reset_success.html"

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect("account:password")
        return super(AccountPasswordResetSuccess, self).dispatch(request, *args, **kwargs)


class AccountPasswordResetLink(FormView):
    template_name = "accounts/password_reset_link.html"
    form_class = AccountPasswordResetLinkForm
    success_url = reverse_lazy('oidc_authentication_init')

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect("account:password")
        return super(AccountPasswordResetLink, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Check reset code kwarg
        reset_code = self.kwargs.get("reset_code")
        if reset_code is None:
            raise Http404(_l("This reset code is not valid."))

        # Check if person exists with this code
        try:
            person = Person.objects.get(password_reset_code=reset_code)
        except Person.DoesNotExist:
            raise Http404(_l("This reset code is not valid."))

        # Check if code is not expired
        if timezone.now() > person.password_reset_expiry:
            person.password_reset_code = None
            person.password_reset_expiry = None
            person.save()
            raise Http404(_l("This reset code is not valid."))

        return super(AccountPasswordResetLink, self).get_context_data(**kwargs)

    def form_valid(self, form):
        reset_code = self.kwargs.get("reset_code")
        if reset_code is None:
            raise Http404(_l("This reset code is not valid."))

        # Get person
        try:
            person = Person.objects.get(password_reset_code=reset_code)
        except Person.DoesNotExist:
            raise Http404(_l("This reset code is not valid."))

        # Check if code is not expired
        if timezone.now() > person.password_reset_expiry:
            person.password_reset_code = None
            person.password_reset_expiry = None
            person.save()
            raise Http404(_l("This reset code is not valid."))

        # Remove reset code
        person.password_reset_code = None
        person.password_reset_expiry = None
        person.save()

        # Reset password
        res, msg = _process_set_password(person.account_name, form.cleaned_data['new_password'])
        if res:
            messages.add_message(request=self.request, level=messages.INFO,
                                 message=_l("Your password was successfully changed. You may now log in."))
            return super(AccountPasswordResetLink, self).form_valid(form)
        else:
            raise ValueError(_l("Error while changing password. {}".format(msg)))


class AccountConfigureForwardingView(RequireActiveMemberMixin, LoginRequiredMixin, TemplateView):
    template_name = "profile_configure_forwarding.html"
    form_class = AccountConfigureForwardingForm

    http_method_names = ['get', 'post']

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)

    def get_context_data(self):
        context = {}

        if self.request.method == "POST":
            context['form'] = self.form_class(self.request.POST)
        else:
            context['form'] = self.form_class()

        # Inject the current forwarding status according to the mapping
        mp = Mapping.wrap(self.request.person)

        if not mp.gsuite_id:
            context['no_gsuite_account'] = True

        else:
            context['is_currently_forwarding'] = mp.gsuite_forwarding_enabled
            context['personal_email'] = self.request.person.email_address
            context['primary_email_domain'] = settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN']
            context['email_domains'] = [settings.CLAUDIA_GSUITE['PRIMARY_DOMAIN']]
            if context['form'].is_valid():
                context['current_step'] = context['form'].cleaned_data['step'] if self.request.method == "POST" else 1
            else:
                context['current_step'] = 1

            if context['current_step'] == 1:
                print("start")

            if context['current_step'] == 2:
                print("adding e-mail "+context['personal_email'])

            if context['current_step'] == 3:
                print("activating forwarding")

        return context


class AccountCheckForwardingStatus(RequireActiveMemberMixin, LoginRequiredMixin, View):
    def get(self, request):
        mp = Mapping.wrap(request.person)

        google = GoogleSuiteAPI()
        forwarding_emails = google.get_user_forwarding_enabled(mp)

        if forwarding_emails['enabled']:
            message = forwarding_emails['emailAddress']
        else:
            message = _l("Unknown, please disable and re-enable forwarding!")

        return HttpJSONResponse({
            'enabled': forwarding_emails['enabled'],
            'email': str(message)
        })


class AccountCheckForwardingVerificationStatus(RequireActiveMemberMixin, LoginRequiredMixin, View):
    def get(self, request):
        mp = Mapping.wrap(request.person)

        google = GoogleSuiteAPI()
        forwarding_emails = google.get_user_forwarding_addresses(mp)
        personal_email = request.person.email_address
        is_verified = personal_email in forwarding_emails.keys() and forwarding_emails[personal_email] == "accepted"

        initial_check = request.GET['initial'] == "1" if 'initial' in request.GET else False

        if is_verified:
            if initial_check:
                message = "<div class=\"icon status_icon icon-accept\"></div><span>" +\
                          str(_l("Your personal e-mail address is already known with Google. "
                                "Click below to activate your e-mail forward.")) +\
                          "</span>"
            else:
                message = "<div class=\"icon status_icon icon-accept\"></div><span>" + \
                          str(_l("Your e-mail address has been verified with Google! "
                                "Click below to activate your e-mail forward.")) + \
                          "</span>"
        else:
            if initial_check:
                message = _l("Your personal e-mail address is not known yet with Google. This has to be verified first. "
                            "Click below to start the verification process.")
            else:
                message = "<div class=\"icon status_icon icon-arrow_rotate_clockwise\"></div><span>" + \
                          str(_l("Your e-mail address has not been verified yet. "
                                "Please check your e-mail for a verification link.")) + \
                          "</span>"

        return HttpJSONResponse({
            'address_verified': is_verified,
            'message': str(message)
        })


class AccountAddForwardingAddress(RequireActiveMemberMixin, LoginRequiredMixin, View):
    def get(self, request):
        mp = Mapping.wrap(request.person)
        google = GoogleSuiteAPI()
        forwarding_emails = google.get_user_forwarding_addresses(mp)
        personal_email = request.person.email_address
        is_verified = personal_email in forwarding_emails.keys() and forwarding_emails[personal_email] == "accepted"

        if not is_verified:
            google.add_user_forwarding_address(mp)
            return HttpJSONResponse({'ok': True})
        else:
            return HttpJSONResponse({'ok': False})


class AccountActivateForwardingAddress(RequireActiveMemberMixin, LoginRequiredMixin, View):
    def get(self, request):
        mp = Mapping.wrap(request.person)
        google = GoogleSuiteAPI()
        forwarding_emails = google.get_user_forwarding_addresses(mp)
        personal_email = request.person.email_address
        is_verified = personal_email in forwarding_emails.keys() and forwarding_emails[personal_email] == "accepted"

        if is_verified:
            google.set_user_enable_forwarding(mp)
            mp.gsuite_forwarding_enabled = True
            mp.save()
            return HttpJSONResponse({
                'ok': True,
                'message': "<div class=\"icon status_icon icon-accept\"></div><span>" +
                           str(_l("Your forward is now activated!")) +
                           "</span>"
            })
        else:
            return HttpJSONResponse({'ok': False})


class AccountDeactivateForwardingAddress(RequireActiveMemberMixin, LoginRequiredMixin, View):
    def get(self, request):
        mp = Mapping.wrap(request.person)
        google = GoogleSuiteAPI()

        google.set_user_disable_forwarding(mp)
        mp.gsuite_forwarding_enabled = False
        mp.save()
        return HttpJSONResponse({
            'ok': True,
            'message': "<div class=\"icon status_icon icon-accept\"></div><span>" +
                       str(_l("Your forward has been deactivated! Don't forget to regularly check "
                             "your Google Suite e-mail so you don't miss anything important!")) +
                       "</span>"
        })

class MailAliasView(RequirePersonMixin, FormView):
    template_name = "accounts/mailing_alias.html"
    form_class = MailAliasForm
    success_url = reverse_lazy('profile_overview')

    def get_form_kwargs(self):
        kwargs = super(MailAliasView, self).get_form_kwargs()
        mp = Mapping.wrap(self.request.person)
        all_groups = AliasGroup.objects.filter(open_to_signup=True)
        kwargs['current'] = [x for x in all_groups if Mapping.find(x) and mp in Mapping.find(x).members()]
        return kwargs

    def form_valid(self, form):
        mp = Mapping.wrap(self.request.person)

        all_groups = AliasGroup.objects.filter(open_to_signup=True)
        current_pks = [x.pk for x in all_groups if Mapping.find(x) and mp in Mapping.find(x).members()]
        current = AliasGroup.objects.filter(pk__in=current_pks)
        new = form.cleaned_data['alias_groups']
        new_pks = [x.pk for x in form.cleaned_data['alias_groups']]

        to_remove = current.exclude(pk__in=new_pks)
        to_add = new.exclude(pk__in=current_pks)

        for alias_group in to_remove:
            alias_group_mp = Mapping.find(alias_group)
            Membership.objects.get(member=mp, group=alias_group_mp).delete()

        for alias_group in to_add:
            alias_group_mp = Mapping.find(alias_group)
            Membership(member=mp, group=alias_group_mp, ad=True, mail=True, description='').save()

        verify_mapping.delay(mp.id)

        return super().form_valid(form)

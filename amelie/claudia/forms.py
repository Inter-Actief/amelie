import datetime
import uuid
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import widgets
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from urllib.parse import urljoin

from amelie.claudia.models import Mapping, AliasGroup, ExtraPersonalAliasEmailValidator, ExtraPersonalAlias
from amelie.claudia.tools import MailAliasModelMultipleChoiceField
from amelie.iamailer import MailTask, Recipient
from amelie.members.models import Person


class SearchMappingForm(forms.Form):
    search = forms.CharField(required=False, label=_('Search'))
    include_inactive = forms.BooleanField(required=False, initial=False, label=_('Also inactive mappings'))
    types = forms.MultipleChoiceField(required=False, choices=sorted([(t, t) for t in Mapping.RELATED_CLASSES]),
                                      widget=forms.CheckboxSelectMultiple, label=_('Types'))


class AccountActivateForm(forms.Form):
    account_name = forms.CharField(max_length=50, label=_('Account name'))
    current_password = forms.CharField(widget=widgets.PasswordInput, label=_('Current password'))
    new_password = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('New password'))
    new_password2 = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('Repeat new password'))

    def clean(self):
        cleaned_data = super(AccountActivateForm, self).clean()
        current_pw = cleaned_data.get("current_password")
        new_pw = cleaned_data.get("new_password")
        new_pw2 = cleaned_data.get("new_password2")

        if current_pw and new_pw and current_pw == new_pw:
            self.add_error("new_password", _("New password must differ from present password"))

        if new_pw and new_pw2 and new_pw != new_pw2:
            self.add_error("new_password2", _("The new passwords do not match"))


class AccountPasswordForm(forms.Form):
    current_password = forms.CharField(widget=widgets.PasswordInput, label=_('Current password'))
    new_password = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('New password'))
    new_password2 = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('Repeat new password'))

    def clean(self):
        cleaned_data = super(AccountPasswordForm, self).clean()
        current_pw = cleaned_data.get("current_password")
        new_pw = cleaned_data.get("new_password")
        new_pw2 = cleaned_data.get("new_password2")

        if current_pw and new_pw and current_pw == new_pw:
            self.add_error("new_password", _("New password must differ from present password"))

        if new_pw and new_pw2 and new_pw != new_pw2:
            self.add_error("new_password2", _("The new passwords do not match"))


class AccountPasswordResetForm(forms.Form):
    account_name = forms.CharField(max_length=50, label=_('Account name'))

    def clean(self):
        cleaned_data = super(AccountPasswordResetForm, self).clean()
        try:
            Person.objects.get(account_name=cleaned_data.get("account_name"))
        except Person.DoesNotExist:
            self.add_error("account_name", _("There is no account with that name."))

    def send_email(self):
        person = Person.objects.get(account_name=self.cleaned_data.get("account_name"))

        # Save reset code in person
        person.password_reset_code = str(uuid.uuid4())
        person.password_reset_expiry = timezone.now() + datetime.timedelta(hours=3)
        person.save()

        mp = Mapping.wrap(person)

        conf = settings.CLAUDIA_MAIL
        language = None
        task = MailTask(from_=conf["FROM"], template_name='accounts/password_reset.mail',
                        report_to=conf["FROM"], report_always=False)

        if 'preferred_language' in mp.extra_data():
            language = mp.extra_data()['preferred_language']

        reset_link = reverse('account:password_reset_link', kwargs={'reset_code': person.password_reset_code})
        reset_link = urljoin(settings.ABSOLUTE_PATH_TO_SITE, reset_link)

        context = {
            'name': mp.name,
            'reset_link': reset_link
        }

        task.add_recipient(Recipient(
            tos=['"{}" <{}>'.format(mp.name, mp.email)],
            context=context,
            language=language
        ))

        # Send e-mail
        task.send(delay=False)


class AccountPasswordResetLinkForm(forms.Form):
    new_password = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('New password'))
    new_password2 = forms.CharField(widget=widgets.PasswordInput, min_length=8, label=_('Repeat new password'))

    def clean(self):
        cleaned_data = super(AccountPasswordResetLinkForm, self).clean()
        new_pw = cleaned_data.get("new_password")
        new_pw2 = cleaned_data.get("new_password2")

        if new_pw and new_pw2 and new_pw != new_pw2:
            self.add_error("new_password2", _("The new passwords do not match"))


class AccountConfigureForwardingForm(forms.Form):
    step = forms.IntegerField()

class MailAliasForm(forms.Form):

    def __init__(self, *args, **kwargs):
        current = kwargs.pop('current')
        super(MailAliasForm, self).__init__(*args, **kwargs)
        self.fields['alias_groups'].initial = current

    alias_groups = MailAliasModelMultipleChoiceField(AliasGroup.objects.filter(open_to_signup=True), required=False,
                                                 widget=widgets.CheckboxSelectMultiple, label=_('Alias groups'))

class PersonalAliasCreateForm(forms.Form):

    email = forms.EmailField(validators=[ExtraPersonalAliasEmailValidator()])

    def clean_email(self):
        if ExtraPersonalAlias.objects.filter(email=self.cleaned_data['email']).count() > 0:
            raise ValidationError(_("This mailaddress is not unique! You might want to make a group."))

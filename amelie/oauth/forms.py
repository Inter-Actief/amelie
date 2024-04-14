from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _


class OAuth2RequestForm(forms.Form):
    application_name = forms.CharField(max_length=50, label=_('The application that will use the OAuth key'))
    member_name = forms.CharField(max_length=50, label=_('The name of the member requesting OAuth access'))
    member_mail = forms.CharField(label=_('The email of the member requesting OAuth access'), widget=widgets.EmailInput)
    redirect_urls = forms.CharField(max_length=500, widget=widgets.Textarea, label=_('A list with on each line a redirect URL'))
    client_type = forms.ChoiceField(choices=(('confidential', _("Confidential")), ('public', _("Public"))), widget=widgets.RadioSelect)
    description = forms.CharField(max_length=250, label=_('A short description of the intended purpose of the application'))

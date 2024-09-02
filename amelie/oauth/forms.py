from django import forms
from django.forms import widgets
from django.utils.translation import ugettext_lazy as _l


class OAuth2RequestForm(forms.Form):
    application_name = forms.CharField(max_length=50, label=_l('The application that will use the OAuth key'))
    member_name = forms.CharField(max_length=50, label=_l('The name of the member requesting OAuth access'))
    member_mail = forms.CharField(label=_l('The email of the member requesting OAuth access'), widget=widgets.EmailInput)
    redirect_urls = forms.CharField(max_length=500, widget=widgets.Textarea, label=_l('A list with on each line a redirect URL'))
    client_type = forms.ChoiceField(choices=(('confidential', _l("Confidential")), ('public', _l("Public"))), widget=widgets.RadioSelect)
    description = forms.CharField(max_length=250, label=_l('A short description of the intended purpose of the application'))

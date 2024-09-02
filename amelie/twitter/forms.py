from django import forms
from django.forms import widgets
from django.template import Template
from django.utils.translation import gettext_lazy as _l

from amelie.style.forms import inject_style
from amelie.twitter.models import TwitterAccount


class TweetForm(forms.Form):
    account = forms.ModelChoiceField(queryset=TwitterAccount.active.filter(is_readonly=False), required=True)
    template = forms.CharField(max_length=140, widget=widgets.Textarea(attrs={'class': 'characters', 'rows':'10', 'cols': '50'}))

    def clean_template(self):
        value = self.cleaned_data['template']

        try:
            t = Template(value)
        except Exception:
            raise forms.ValidationError(_l("Invalid template"))
        return value

    def send_tweet(self):
        account = value = self.cleaned_data['account'].get_twython_instance()
        account.updateStatus(status=self.cleaned_data['template'])
        return True

inject_style(TweetForm)

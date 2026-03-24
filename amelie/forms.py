from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _l

from amelie.style.forms import inject_style


class AmelieAuthenticationForm(AuthenticationForm):
    remain_logged_in = forms.BooleanField(required=False, label=_l('Stay logged in'))


inject_style(AmelieAuthenticationForm)

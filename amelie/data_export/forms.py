from django import forms
from django.forms import CheckboxSelectMultiple
from django.utils.translation import gettext_lazy as _

from amelie.data_export.models import ApplicationStatus
from amelie.style.forms import inject_style


class DataExportCreateForm(forms.Form):
    applications = forms.MultipleChoiceField(choices=ApplicationStatus.ApplicationChoices.choices,
                                             widget=CheckboxSelectMultiple,
                                             label=_("For which things do you want to request a data export?"),
                                             help_text=_("Which applications, files or other data this data export has to contain."),
                                             # Turn on all options by default.
                                             initial=[c for c in ApplicationStatus.ApplicationChoices.values
                                                      if ApplicationStatus.APPLICATION_MODELS[c].default_enabled])


inject_style(DataExportCreateForm)

import os
from datetime import timedelta

from django import forms
from django.conf import settings
from django.db.models import BLANK_CHOICE_DASH, TextChoices
from django.forms import widgets
from django.forms import BoundField
from django.template.utils import get_app_template_dirs
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from amelie.style.forms import inject_style
from amelie.members.models import LANGUAGE_CHOICES
from amelie.tools.models import DataExportInformation
from amelie.tools.widgets import DateTimeSelector


def attach_hidden(form):
    def as_hidden(self):
        """
        Returns this form rendered entirely as hidden fields.
        """
        output = []
        for name, field in self.fields.items():
            bf = BoundField(self, field, name)
            output.append(bf.as_hidden())
        return '\n'.join(output)

    form.as_hidden = mark_safe(as_hidden(form))


class PeriodForm(forms.Form):
    from_date = forms.DateField(label='Begin date:', initial=timezone.now().date() - timedelta(days=365))
    to_date = forms.DateField(label='End date:', initial=timezone.now().date())

    def __init__(self, *args, **kwargs):
        if 'to_date_required' in kwargs:
            to_date_required = kwargs['to_date_required']
            del kwargs['to_date_required']
        else:
            to_date_required = True

        super(PeriodForm, self).__init__(*args, **kwargs)

        self.fields["to_date"].required = to_date_required


inject_style(PeriodForm)

class PeriodKeywordForm(forms.Form):
    keywords = forms.CharField(max_length=20, label=_('Keywords'))
    from_date = forms.DateField(label=_('Begin date:'), initial=timezone.now().date() - timedelta(days=365))
    to_date = forms.DateField(label=_('End date:'), initial=timezone.now().date())

    def __init__(self, *args, **kwargs):
        if 'to_date_required' in kwargs:
            to_date_required = kwargs['to_date_required']
            del kwargs['to_date_required']
        else:
            to_date_required = True

        if 'keywords_required' in kwargs:
            keywords_required = kwargs['keywords_required']
            del kwargs['keywords_required']
        else:
            keywords_required = True

        super(PeriodKeywordForm, self).__init__(*args, **kwargs)

        self.fields["to_date"].required = to_date_required
        self.fields["keywords"].required = keywords_required


inject_style(PeriodKeywordForm)

class PeriodTimeForm(forms.Form):
    datetime_from = forms.SplitDateTimeField(label='Begin:', initial=timezone.now() - timedelta(days=365), widget=DateTimeSelector)
    datetime_to = forms.SplitDateTimeField(label='End:', initial=timezone.now(), widget=DateTimeSelector)

    def __init__(self, *args, **kwargs):
        if 'datetime_to_required' in kwargs:
            datetime_to_required = kwargs['datetime_to_required']
            del kwargs['datetime_to_required']
        else:
            datetime_to_required = True

        super(PeriodTimeForm, self).__init__(*args, **kwargs)

        self.fields["datetime_to"].required = datetime_to_required


inject_style(PeriodTimeForm)


class DateTimeForm(forms.Form):
    datetime = forms.SplitDateTimeField(label='Date/time:', initial=timezone.now(), widget=DateTimeSelector)


inject_style(DateTimeForm)


def _mail_templates():
    mail_templates = []
    TEMPLATE_DIRS = []
    for t in settings.TEMPLATES:
        if 'DIRS' in t:
            TEMPLATE_DIRS += t['DIRS']

    # Recursively find all *.mail templates in all template directories
    dirs = TEMPLATE_DIRS + list(get_app_template_dirs('templates'))
    for template_dir in dirs:
        for dir_path, dir_names, filenames in os.walk(template_dir):
            for filename in filenames:
                if filename.endswith('.mail'):
                    template_file = os.path.join(dir_path, filename)

                    if template_file.startswith(str(template_dir)):
                        template_name = os.path.relpath(template_file, template_dir)
                        mail_templates.append(template_name)
                    else:
                        raise ValueError('Invalid template filename')

    mail_templates.sort()

    return [(mt, mt) for mt in mail_templates]


class MailTemplateTestForm(forms.Form):
    class Formats(TextChoices):
        HTML = 'html', _("HTML")
        PLAIN = 'plain', _("Plain text")

    template = forms.ChoiceField(label=_('Template'), choices=_mail_templates())
    language = forms.ChoiceField(label=_('Language'), choices=LANGUAGE_CHOICES, initial='nl')
    format = forms.ChoiceField(label=_('Template'), choices=Formats.choices)


class ExportTypeSelectForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(ExportTypeSelectForm, self).__init__(*args, **kwargs)

        choices = BLANK_CHOICE_DASH + [(x, x) for x in DataExportInformation.objects.values_list('export_type', flat=True).distinct().order_by()]

        self.fields['export_type'] = forms.ChoiceField(
            choices=choices,
            required=False,
            widget=forms.Select(),
            initial="",
            label=_("Only show exports of this type")
        )


class ExportForm(forms.Form):
    export_type = forms.CharField(max_length=100, required=False, widget=widgets.HiddenInput())
    export_details = forms.CharField(max_length=512, required=False, widget=widgets.HiddenInput())
    reason = forms.CharField(max_length=512, label=_('Reason for export'), widget=widgets.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, rows=None, **kwargs):
        super(ExportForm, self).__init__(*args, **kwargs)
        if rows is not None:
            self.fields['reason'].widget.attrs['rows'] = rows

    def clean(self):
        cleaned_data = super(ExportForm, self).clean()
        if 'member_export_csv' in self.data:
            cleaned_data['export_type'] = 'member_export_csv'
        elif 'member_export_vcf' in self.data:
            cleaned_data['export_type'] = 'member_export_vcf'
        elif 'member_export_email' in self.data:
            cleaned_data['export_type'] = 'member_export_email'
        elif 'cookie_corner_sepa_export' in self.data:
            cleaned_data['export_type'] = 'cookie_corner_sepa_export'
        elif 'activity_export_deanonymise' in self.data:
            cleaned_data['export_type'] = 'activity_export_deanonymise'
        elif 'activity_export_csv' in self.data:
            cleaned_data['export_type'] = 'activity_export_csv'
        elif 'activity_export_print' in self.data:
            cleaned_data['export_type'] = 'activity_export_print'
        else:
            raise forms.ValidationError(_("Unknown data export type."))

        return cleaned_data

    def save_data_export_information(self, person):
        """
        Construct and save a DataExportInformation object, and then return its ID and the type that was exported.
        :param person: The person that is exporting the data.
        :return: Tuple of the ID of the new DataExportInformation object and the export type of the data that was given.
        """
        dei_id = DataExportInformation.objects.create(**{
            'export_type': self.cleaned_data['export_type'],
            'details': self.cleaned_data['export_details'],
            'reason': self.cleaned_data['reason'],
            'exporter': person
        })

        return dei_id, self.cleaned_data['export_type']


inject_style(MailTemplateTestForm, ExportTypeSelectForm, ExportForm)

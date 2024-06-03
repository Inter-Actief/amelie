from django import forms
from django.contrib.admin.widgets import AdminFileWidget
from django.core.files.images import get_image_dimensions
from django.forms import SplitDateTimeField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _l

from amelie.companies.models import Company, WebsiteBanner, TelevisionBanner, CompanyEvent, VivatBanner
from amelie.style.forms import inject_style
from amelie.calendar.forms import EventForm
from amelie.tools.widgets import DateTimeSelector, DateSelector


class CompanyForm(forms.ModelForm):
    logo = forms.FileField(label=_l('Logo'), widget=AdminFileWidget)
    app_logo = forms.FileField(label=_l('App Logo'), widget=AdminFileWidget, required=False)
    start_date = forms.DateField(widget=DateSelector, label=_l('From'))
    end_date = forms.DateField(widget=DateSelector, label=_l('Until'))
    short_description_nl = forms.CharField(
        max_length=120,
        label=_l('Short description'),
        help_text=_l('This text can be laid-out in 120 characters'),
        widget=forms.Textarea,
        required=False
    )
    short_description_en = forms.CharField(
        max_length=120,
        label=_l('Short description'),
        help_text=_l('This text can be laid-out in 120 characters'),
        widget=forms.Textarea,
        required=False
    )

    class Meta:
        model = Company
        fields = ['name_nl',
                  'name_en',
                  'url',
                  'start_date',
                  'end_date',
                  'show_in_app',
                  'logo',
                  'app_logo',
                  'profile_nl',
                  'profile_en',
                  'short_description_nl',
                  'short_description_en'
        ]

    def clean_app_logo(self):
        app_logo = self.cleaned_data.get("app_logo")

        if app_logo:
            w, h = get_image_dimensions(app_logo)
            min_w, min_h = 1024, 1024

            if w > min_w or h > min_h:
                raise forms.ValidationError(_l("The thumbnail logo's size is %(w)dpx by %(h)dpx, while the maximum allowed size is %(min_w)dpx by %(min_h)dpx.") %
                                            {'w': w, 'h': h, 'min_w': min_w, 'min_h': min_h})

        return app_logo


class BannerForm(forms.ModelForm):
    picture = forms.ImageField(label=_l('Website banner'), widget=AdminFileWidget)
    start_date = forms.DateField(widget=DateSelector)
    end_date = forms.DateField(widget=DateSelector)

    class Meta:
        model = WebsiteBanner
        fields = ["picture", "name", 'start_date', "end_date", 'active', 'url']


class TelevisionBannerForm(forms.ModelForm):
    picture = forms.ImageField(label=_l('Television banner'), widget=AdminFileWidget)
    start_date = forms.DateField(widget=DateSelector)
    end_date = forms.DateField(widget=DateSelector)

    class Meta:
        model = TelevisionBanner
        fields = ["picture", "name", 'start_date', "end_date", 'active']


class VivatBannerForm(forms.ModelForm):
    picture = forms.FileField(label=_l('Vivat banner'), widget=AdminFileWidget)
    start_date = forms.DateField(widget=DateSelector)
    end_date = forms.DateField(widget=DateSelector)

    class Meta:
        model = VivatBanner
        fields = ["picture", "name", 'start_date', "end_date", 'active', 'url']


class CompanyEventForm(EventForm):
    company = forms.ModelChoiceField(queryset=Company.objects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now()), required=False)

    class Meta:
        model = CompanyEvent

        widgets = {
            'begin': DateTimeSelector,
            'end': DateTimeSelector,
            "enrollment_begin": DateTimeSelector,
            "enrollment_end": DateTimeSelector,
            "visible_from": DateTimeSelector,
            "visible_till": DateTimeSelector
        }
        field_classes = {
            'begin': SplitDateTimeField,
            'end': SplitDateTimeField,
            "enrollment_begin": SplitDateTimeField,
            "enrollment_end": SplitDateTimeField,
            "visible_from": SplitDateTimeField,
            "visible_till": SplitDateTimeField,
        }

        fields = ['summary_nl', 'summary_en', 'location', 'begin', 'end', "visible_from", "visible_till",
                  "company", "company_text", "company_url", 'description_nl', 'description_en', 'dutch_activity']

    def clean(self):
        super(CompanyEventForm, self).clean()

        data = self.cleaned_data
        b = data.get('company', False)

        visible_from = data.get('visible_from', False)
        visible_till = data.get('visible_till', False)

        if not (b or (data.get('company_text', None) and data.get('company_url', None))):
            raise forms.ValidationError({"company": [_l("Company Corner company or name/website is obligatory.")]})

        if visible_from and visible_till and data['visible_from'] > data['visible_till']:
            raise forms.ValidationError({"visible_from": [_l(u'Activity\'s "visible from" date is later than its "visible until" date')]})

        return data


class StatisticsForm(forms.Form):
    start_date = forms.SplitDateTimeField(label=_l('Beginning:'), widget=DateTimeSelector, required=True)
    end_date = forms.SplitDateTimeField(label=_l('End (till)'), widget=DateTimeSelector, required=True)


inject_style(CompanyForm, CompanyEventForm, BannerForm, TelevisionBannerForm, VivatBannerForm, StatisticsForm)

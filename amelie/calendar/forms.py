from django import forms
from django.forms import SplitDateTimeField

from amelie.style.forms import inject_style
from amelie.calendar.models import Event
from amelie.tools.widgets import DateTimeSelector


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        widgets = {
            'begin': DateTimeSelector,
            'end': DateTimeSelector,
            "enrollment_begin": DateTimeSelector,
            "enrollment_end": DateTimeSelector,
        }
        field_classes = {
            'begin': SplitDateTimeField,
            'end': SplitDateTimeField,
            "enrollment_begin": SplitDateTimeField,
            "enrollment_end": SplitDateTimeField,
        }

        fields = ['summary_nl', 'summary_en', 'location', 'begin', 'end', 'organizer', 'description_nl',
                  'description_en', 'public', 'dutch_activity', 'callback_url', 'callback_secret_key',
                  'entire_day', 'attachments', ]


inject_style(EventForm)

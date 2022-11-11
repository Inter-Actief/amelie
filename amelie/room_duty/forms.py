from django import forms
from django.forms import SplitDateTimeField, DurationField

from amelie.style.forms import inject_style
from amelie.room_duty.models import RoomDutyTableTemplate, RoomDutyTable, RoomDutyPool, RoomDutyTemplate, RoomDuty, \
    RoomDutyAvailability, BalconyDutyAssociation
from amelie.tools.widgets import DateTimeSelector, SplitDurationWidget


class RoomDutyTableForm(forms.ModelForm):
    template = forms.ModelChoiceField(RoomDutyTableTemplate.objects, required=False)
    pool = forms.ModelChoiceField(RoomDutyPool.objects, required=False)

    class Meta:
        model = RoomDutyTable
        fields = ["title", 'begin', 'balcony_duty']
        widgets = {
            'begin': DateTimeSelector,
        }
        field_classes = {
            'begin': SplitDateTimeField
        }


class RoomDutyTableChangeForm(forms.ModelForm):
    class Meta:
        model = RoomDutyTable
        fields = ["title", 'balcony_duty']


class BalconyDutyAssociationForm(forms.ModelForm):
    class Meta:
        model = BalconyDutyAssociation
        fields = ['association', 'is_this_association']


class RoomDutyPoolForm(forms.ModelForm):
    class Meta:
        model = RoomDutyPool
        fields = ['name']


class RoomDutyTableTemplateForm(forms.ModelForm):
    class Meta:
        model = RoomDutyTableTemplate
        fields = ["title"]


class RoomDutyTemplateForm(forms.ModelForm):
    class Meta:
        model = RoomDutyTemplate
        fields = ['begin', 'end']
        widgets = {
            'begin': SplitDurationWidget,
            'end': SplitDurationWidget
        }
        field_classes = {
            'begin': DurationField,
            'end': DurationField,
        }


class RoomDutyForm(forms.ModelForm):
    class Meta:
        model = RoomDuty
        fields = ['begin', 'end']
        widgets = {
            'begin': DateTimeSelector,
            'end': DateTimeSelector
        }
        field_classes = {
            'begin': SplitDateTimeField,
            'end': SplitDateTimeField,
        }


class RoomDutyAvailabilityForm(forms.ModelForm):
    class Meta:
        model = RoomDutyAvailability
        fields = ['availability', 'hungover', 'not_in_the_break', 'comments']


class RoomDutyParticipantForm(forms.ModelForm):
    participant_set = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, **kwargs):
        super(RoomDutyParticipantForm, self).__init__(*args, **kwargs)
        self.fields['participant_set'].choices = self.get_choices

    def get_choices(self):
        persons = self.instance.table.persons
        return [(person.pk, str(person)) for person in persons]

    class Meta:
        model = RoomDuty
        fields = ['participant_set']


inject_style(RoomDutyTableForm, RoomDutyTableChangeForm, RoomDutyPoolForm, RoomDutyTableTemplateForm,
             RoomDutyTemplateForm, RoomDutyForm, RoomDutyAvailabilityForm, RoomDutyParticipantForm)

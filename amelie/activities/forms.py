import logging
from datetime import timedelta
from decimal import Decimal
from typing import OrderedDict, Optional, Tuple, List

from betterforms.multiform import MultiForm
from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from django.core.validators import FileExtensionValidator
from django.forms import widgets, SplitDateTimeField
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _l

from amelie.activities.models import Activity, EnrollmentoptionQuestion, \
    EnrollmentoptionCheckbox, EnrollmentoptionCheckboxAnswer, \
    EnrollmentoptionQuestionAnswer, EnrollmentoptionFood, \
    EnrollmentoptionFoodAnswer, Restaurant, EnrollmentoptionNumericAnswer, EnrollmentoptionNumeric, ActivityLabel, \
    EnrollmentoptionAnswer
from amelie.calendar.models import Participation
from amelie.members.models import Person, Committee
from amelie.tools.forms import MultipleFileField
from amelie.tools.widgets import DateTimeSelector, DateTimeSelectorWithToday


class ActivityForm(forms.ModelForm):
    price = forms.DecimalField(required=False, initial="0.00", min_value=0, decimal_places=2, label=_l('Price'), help_text=_l('Enrolled participants will be emailed when you change the price.'))

    class Meta:
        model = Activity
        fields = (
            'summary_nl', 'summary_en', 'location', 'begin', 'end', 'organizer', 'activity_label', 'promo_nl', 'promo_en',
            'description_nl', 'description_en', "public", 'dutch_activity', "enrollment", "enrollment_private",
            "can_unenroll", "enrollment_begin", "enrollment_end", 'maximum', "waiting_list_locked", "price",
            "image_icon", 'callback_url', 'callback_secret_key', 'facebook_event_id', 'oauth_application'
        )
        field_classes = {
            'begin': SplitDateTimeField,
            'end': SplitDateTimeField,
            "enrollment_begin": SplitDateTimeField,
            "enrollment_end": SplitDateTimeField
        }
        widgets = {
            'begin': DateTimeSelector,
            'end': DateTimeSelector,
            "enrollment_begin": DateTimeSelectorWithToday,
            "enrollment_end": DateTimeSelector,
        }

    def __init__(self, person=None, current_organizer_pk=None, *args, **kwargs):
        if not person:
            raise Exception("ActiviteitForm requires a parameter person")

        super(ActivityForm, self).__init__(*args, **kwargs)
        if person.is_board() or person.user.is_staff:
            committees = Committee.objects.active()
            labels = ActivityLabel.objects.all()
            if current_organizer_pk:
                # Join the current organizer, since the committee may have turned inactive
                committees |= Committee.objects.filter(pk=current_organizer_pk)
        else:
            committees = Committee.objects.active().filter(function__person=person, function__end__isnull=True)
            labels = ActivityLabel.objects.filter(active=True)
        self.fields['activity_label'].queryset = labels
        self.fields['organizer'] = forms.ModelChoiceField(committees)

    def clean(self):
        if not self.cleaned_data.get('price', None):
            self.cleaned_data['price'] = 0

        if self.cleaned_data["price"] > settings.PERSONAL_TAB_MAXIMUM_ACTIVITY_PRICE and self.cleaned_data["enrollment"]:
            raise forms.ValidationError(_l("Website enrolment has a maximum of {0} euro. Either turn off the ability to enrol or decrease the cost of the activity.").format(settings.PERSONAL_TAB_MAXIMUM_ACTIVITY_PRICE))

        if self.cleaned_data["enrollment"]:
            if not self.cleaned_data.get('enrollment_begin', None):
                self.add_error('enrollment_begin', _l('There is no enrollment start date entered.'))

            if not self.cleaned_data.get('enrollment_end'):
                self.add_error('enrollment_end', _l('There is no enrollment end date entered.'))

            if self.cleaned_data.get('enrollment_begin', None) and self.cleaned_data.get('enrollment_stop', None) \
                    and self.cleaned_data['enrollment_stop'] < self.cleaned_data['enrollment_begin']:
                self.add_error('enrollment_stop', _l("Signup end must be after the signup start."))

        return self.cleaned_data


class IndirectEnrollmentForm(forms.Form):
    def __init__(self, waiting_list=False, board=False, *args, **kwargs):
        super(IndirectEnrollmentForm, self).__init__(*args, **kwargs)

        if waiting_list:
            self.fields['waiting_list'] = forms.ChoiceField(choices=[
                ('wait', _l("Place on bottom of waiting list")),
            ], label=_l("Waiting list action"))
            if board:
                choices = self.fields['waiting_list'].choices
                choices.append(('skip', _l("Skip waiting list and enroll immediately")))
                self.fields['waiting_list'].choices = choices


class EnrollmentoptionQuestionForm(forms.ModelForm):
    class Meta:
        model = EnrollmentoptionQuestion
        fields = ["title", 'required']


class EnrollmentoptionCheckboxForm(forms.ModelForm):
    class Meta:
        model = EnrollmentoptionCheckbox
        fields = ["title", "price_extra", "maximum"]


class EnrollmentoptionNumericForm(forms.ModelForm):
    class Meta:
        model = EnrollmentoptionNumeric
        fields = ["title", "price_extra", "maximum", "maximum_per_person"]


class EnrollmentoptionFoodForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(EnrollmentoptionFoodForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)

        if instance and instance.pk: # Only make the last chosen restaurant available, this may not change.
            self.fields['restaurant'].queryset = Restaurant.objects.filter(id=instance.restaurant.id)
            self.fields['restaurant'].empty_label = None
        else:
            self.fields['restaurant'].queryset = Restaurant.objects.filter(available=True)

    def clean_restaurant(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk: # Restaurant may not be changed, even if you bypass the form.
            return instance.restaurant
        else:
            return self.cleaned_data['restaurant']

    class Meta:
        model = EnrollmentoptionFood
        fields = ["title", 'required', 'restaurant']


class EnrollmentoptionAnswerForm(forms.ModelForm):
    def __init__(self, enrollmentoption, *args, **kwargs):
        if 'checked' in kwargs:
            del kwargs['checked']
        super(EnrollmentoptionAnswerForm, self).__init__(*args, **kwargs)
        self.enrollmentoption = enrollmentoption

    def enrollmentoption_type(self):
        return self.enrollmentoption.__class__.__name__

    class Meta:
        fields = []


class EnrollmentoptionQuestionAnswerForm(EnrollmentoptionAnswerForm):
    class Meta:
        model = EnrollmentoptionQuestionAnswer
        fields = ("answer",)


class EnrollmentoptionCheckboxAnswerForm(EnrollmentoptionAnswerForm):

    def __init__(self, enrollmentoption, checked, *args, **kwargs):
        super(EnrollmentoptionCheckboxAnswerForm, self).__init__(enrollmentoption, *args, **kwargs)
        if not enrollmentoption.spots_left() and not checked:
            self.fields["answer"].widget.attrs['disabled'] = True

    def clean_answer(self):
        data = self.cleaned_data['answer']
        if data and not self.enrollmentoption.spots_left():
            self.add_error('answer', _l("Sorry, but the last spot has been claimed already!"))
        return data

    class Meta:
        model = EnrollmentoptionCheckboxAnswer
        fields = ("answer",)


class EnrollmentoptionNumericAnswerForm(EnrollmentoptionAnswerForm):

    def __init__(self, enrollmentoption, checked, *args, **kwargs):
        super(EnrollmentoptionNumericAnswerForm, self).__init__(enrollmentoption, *args, **kwargs)
        self.fields["answer"].required = False
        if not enrollmentoption.spots_left() and not checked:
            self.fields["answer"].widget.attrs['disabled'] = True

    def clean_answer(self):
        data = self.cleaned_data['answer']
        max_per_person = self.enrollmentoption.maximum_per_person if self.enrollmentoption.maximum_per_person > 0 else None
        if not data:
            data = 0
        if max_per_person is not None and data > max_per_person:
            self.add_error('answer', _l("Sorry, but you cannot exceed the maximum amount per person!"))
        if data > 0 and not self.enrollmentoption.spots_left():
            self.add_error('answer', _l("Sorry, but there are not enough spots left!"))
        return data

    class Meta:
        model = EnrollmentoptionNumericAnswer
        fields = ("answer",)


class EnrollmentoptionFoodAnswerForm(EnrollmentoptionAnswerForm):
    def __init__(self, enrollmentoption, *args, **kwargs):
        super(EnrollmentoptionFoodAnswerForm, self).__init__(enrollmentoption, *args, **kwargs)
        self.fields['dishprice'].queryset = enrollmentoption.dishprice_set

    class Meta:
        model = EnrollmentoptionFoodAnswer
        fields = ("dishprice",)


ENROLLMENTOPTION_FORM_TYPES = {
    EnrollmentoptionQuestion: EnrollmentoptionQuestionForm,
    EnrollmentoptionCheckbox: EnrollmentoptionCheckboxForm,
    EnrollmentoptionFood: EnrollmentoptionFoodForm,
    EnrollmentoptionNumeric: EnrollmentoptionNumericForm,
}


class ActivityEnrollmentOptionsForm(MultiForm):
    ENROLLMENTOPTION_ANSWER_TYPES = {
        EnrollmentoptionQuestion: EnrollmentoptionQuestionAnswer,
        EnrollmentoptionCheckbox: EnrollmentoptionCheckboxAnswer,
        EnrollmentoptionFood: EnrollmentoptionFoodAnswer,
        EnrollmentoptionNumeric: EnrollmentoptionNumericAnswer,
    }

    ENROLLMENTOPTIONANSWER_FORM_TYPES = {
        EnrollmentoptionQuestion: EnrollmentoptionQuestionAnswerForm,
        EnrollmentoptionCheckbox: EnrollmentoptionCheckboxAnswerForm,
        EnrollmentoptionFood: EnrollmentoptionFoodAnswerForm,
        EnrollmentoptionNumeric: EnrollmentoptionNumericAnswerForm,
    }

    form_classes = OrderedDict([])

    def __init__(self, activity: Activity, *args, participation: Optional[Participation] = None, add_indirect_form: bool = False, **kwargs):
        # Built the forms for the enrollment options
        self.form_classes = OrderedDict([])
        self.activity = activity
        self.participation = participation

        initials = kwargs.get('initial', {})  # Reference to add the EnrollmentOptionForm initial data to.

        if add_indirect_form:
            self.form_classes['indirect'] = IndirectEnrollmentForm

        for enrollmentoption in activity.enrollmentoption_set.all():
            prefix = 'enrollmentoption_{}'.format(enrollmentoption.pk)

            answer_type: type[EnrollmentoptionAnswer] = ActivityEnrollmentOptionsForm.ENROLLMENTOPTION_ANSWER_TYPES[enrollmentoption.content_type.model_class()]
            content_type = ContentType.objects.get_for_model(answer_type)

            # Try to resolve the instance to an actual object if the person is enrolled for the activity
            instance: EnrollmentoptionAnswer = answer_type(enrollmentoption=enrollmentoption, content_type=content_type)
            if participation is not None:
                try:
                    instance: EnrollmentoptionAnswer = answer_type.objects.get(
                        enrollment=participation,
                        enrollmentoption=enrollmentoption,
                        content_type=content_type
                    )
                except EnrollmentoptionAnswer.DoesNotExist:
                    pass

            form_type: type[EnrollmentoptionAnswerForm] = ActivityEnrollmentOptionsForm.ENROLLMENTOPTIONANSWER_FORM_TYPES[enrollmentoption.content_type.model_class()]

            # Make sure that if someone adjusts their enrollment, and they have a spot with a limited capacity,
            # they can still keep their spot.
            checked = False
            if instance.pk:
                if form_type == EnrollmentoptionCheckboxAnswerForm:
                    instance: EnrollmentoptionCheckboxAnswer
                    checked = instance.answer
                elif form_type == EnrollmentoptionNumericAnswerForm:
                    instance: EnrollmentoptionNumericAnswer
                    checked = instance.answer > 0

            # Add the enrollment option form to the MultiForm
            self.form_classes[prefix] = form_type
            initials[prefix] = {
                'enrollmentoption': enrollmentoption,
                'checked': checked,
                'prefix': prefix,
                'instance': instance
            }
        super().__init__(*args, **kwargs)

    def get_form_args_kwargs(self, key, args, kwargs):
        args, fkwargs = super().get_form_args_kwargs(key=key, args=args, kwargs=kwargs)
        # Extra per-form kwargs are stored in the initial values for the forms, which also includes a nested 'initial' key for the actual initial values.
        fkwargs['initial'] = None
        fkwargs.update(**self.initials.get(key, {}))
        logging.error(f"Form {key} - args {args}, fkwargs {fkwargs}")  # TODO REMOVE
        return args, fkwargs

    def get_costs(self) -> Tuple[Decimal, Decimal, bool]:
        if not self.is_valid():
            raise ValueError("Cannot calculate costs. The forms are not valid.")
        answers = [f.save(commit=False) for f in self.forms.values() if isinstance(f, EnrollmentoptionAnswerForm)]
        prices_extra: List[Decimal] = [enrollment_option_answer.get_price_extra() for enrollment_option_answer in answers]
        return self.activity.price, Decimal(sum(prices_extra)), len(prices_extra) > 0


class ActivityModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s (%s)" % (obj.summary, formats.date_format(obj.begin))


class PhotoCheckboxSelectMultiple(widgets.CheckboxSelectMultiple):
    option_template_name = 'photo_upload_checkbox_option.html'


class PhotoUploadForm(forms.Form):
    photographer = forms.ModelChoiceField(Person.objects.none(), label=_l('Photographer'), required=False)
    first_name = forms.CharField(max_length=50, label=_l('First name'), required=False,
                                 help_text=_l('Use this field if a non-member is the owner of these pictures'))
    last_name_prefix = forms.CharField(max_length=25, label=_l('Last name pre-fix'), required=False,
                                       help_text=_l('Use this field if a non-member is the owner of these pictures'))
    last_name = forms.CharField(max_length=50, label=_l('Last name'), required=False,
                                help_text=_l('Use this field if a non-member is the owner of these pictures'))
    activity = ActivityModelChoiceField(Activity.objects.none(), label=_l('Activities'))
    public = forms.BooleanField(label=_l('Public'), required=False,
                                help_text=_l('Photos are also available without logging in'), initial=True)
    photos = forms.MultipleChoiceField(widget=PhotoCheckboxSelectMultiple, label=_l('Photos'))

    def __init__(self, photos, *args, **kwargs):
        super(PhotoUploadForm, self).__init__(*args, **kwargs)
        self.fields['photos'].choices = photos
        self.fields['activity'].queryset = Activity.objects.filter(
            begin__lt=timezone.now(), begin__gte=timezone.now() - timedelta(days=365)
        ).order_by('-begin', '-end')
        self.fields['photographer'].queryset = Person.objects.filter(function__begin__isnull=False,
                                                                     function__end__isnull=True).distinct().order_by('first_name', 'last_name')

    def clean(self):
        clean_data = super().clean()
        #Check whether there is a proper photographer
        if not self.cleaned_data['photographer'] and not self.cleaned_data['first_name'] is None:
            raise forms.ValidationError(_l('You must specify a photographer!'), code='required')

        if self.cleaned_data['first_name'] and not self.cleaned_data['last_name']:
            raise forms.ValidationError(_l('You must specify a last name!'), code='required')

        if self.cleaned_data['last_name'] and not self.cleaned_data['first_name']:
            raise forms.ValidationError(_l('You must specify a first name!'), code='required')

        return clean_data

class PhotoFileUploadForm(forms.Form):
    allowed_extensions = ["jpg", "jpeg", "gif"]
    photo_files = MultipleFileField(accept=','.join(map(lambda ext: f'image/{ext}', allowed_extensions)))

    def clean_photo_files(self):
        validator = FileExtensionValidator(allowed_extensions=self.allowed_extensions)

        for file in self.files.getlist('photo_files'):
            # FileExtensionValidator raises ValidationError if an extension is not allowed
            validator(file)


class EventDeskActivityMatchForm(forms.Form):
    activity = ActivityModelChoiceField(Activity.objects.none(), label=_l('Activity'))

    def __init__(self, activities, *args, **kwargs):
        super(EventDeskActivityMatchForm, self).__init__(*args, **kwargs)
        self.fields['activity'].queryset = activities

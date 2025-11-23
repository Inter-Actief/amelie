from django import forms
from django.conf import settings
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy as _l
from localflavor.generic.forms import BICFormField, IBANFormField

from amelie.members.models import Person
from amelie.style.forms import inject_style
from amelie.personal_tab import statistics
from amelie.personal_tab.models import CustomTransaction, CookieCornerTransaction, RFIDCard, Reversal, AuthorizationType, \
    DebtCollectionBatch, Authorization
from amelie.tools.widgets import DateSelector, DateTimeSelector, MemberSelect


class CustomTransactionForm(forms.ModelForm):
    date = forms.SplitDateTimeField(label=_l('Date'), widget=DateTimeSelector, initial=timezone.now)

    class Meta:
        model = CustomTransaction
        fields = ['date', 'price', 'description']


class CookieCornerTransactionForm(forms.ModelForm):
    date = forms.SplitDateTimeField(label=_l('Date'), widget=DateTimeSelector, initial=timezone.now)

    class Meta:
        model = CookieCornerTransaction
        fields = ['date', 'price', 'description', 'article', 'amount']


class ExamCookieCreditForm(forms.Form):
    price = forms.DecimalField(max_digits=8, decimal_places=2, label=_l('Price'))
    description = forms.CharField(max_length=200, label=_l('Description'))


class PersonSpendingLimitsForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('cookie_corner_budget', 'cookie_corner_budget_action')


class DebtCollectionForm(forms.Form):
    description = forms.CharField(max_length=50, label=_l('Description for within Inter-Actief'))
    execution_date = forms.DateField(label=_l('Date of execution'), widget=DateSelector)
    contribution = forms.BooleanField(required=False, label=_l('Membership fee'))
    cookie_corner = forms.BooleanField(required=False, label=_l('Personal tab'))
    end = forms.SplitDateTimeField(label=_l('Transactions until'), widget=DateTimeSelector)

    def __init__(self, minimal_execution_date, *args, **kwargs):
        super(DebtCollectionForm, self).__init__(*args, **kwargs)
        self.minimal_execution_date = minimal_execution_date
        self.fields['execution_date'].initial = minimal_execution_date

    def clean_execution_date(self):
        data = self.cleaned_data['execution_date']
        if data < self.minimal_execution_date:
            raise forms.ValidationError(_l('Date of execution is too soon'))
        if data.weekday() >= 5:  # Saturday or sunday
            raise forms.ValidationError(_l('Date of execution cannot be during the weekend'))

        # Always return the cleaned data, whether you have changed it or not.
        return data


class ReversalForm(forms.ModelForm):
    class Meta:
        model = Reversal
        fields = ['date', 'pre_settlement', 'reason']


class DebtCollectionBatchForm(forms.ModelForm):
    class Meta:
        model = DebtCollectionBatch
        fields = ('status',)


class AmendmentForm(forms.Form):
    """Form to enter an amendment"""

    """Date of the amendment"""
    date = forms.DateField(label=_l('Date'))

    """IBAN for authorization"""
    iban = IBANFormField(label=_l('IBAN'))

    """BIC for authorization"""
    bic = BICFormField(label=_l('BIC*'), required=False)

    """Short description of the reason of this amendment."""
    reason = forms.CharField(max_length=250, label=_l('Remarks'),
                             help_text=_l('Short description of the reason for the amendment'))

    def clean(self):
        cleaned_data = super(AmendmentForm, self).clean()
        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if not cleaned_data['bic']:
            if not cleaned_data['iban'][:2] == 'NL':
                self.add_error('bic', _l('BIC has to be entered for foreign bank accounts.'))
            elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
            else:
                self.add_error('bic', _l('BIC could not be generated, please enter yourself.'))
        return cleaned_data


inject_style(CustomTransactionForm, CookieCornerTransactionForm, ExamCookieCreditForm, DebtCollectionForm, ReversalForm,
             AmendmentForm)


class SearchAuthorizationForm(forms.Form):
    class AuthorizationStatuses(TextChoices):
        UNSIGNED = 'unsigned', _l("Not signed")
        ACTIVE = 'active', _l("Active")
        TERMINATED = 'terminated', _l("Ended")

    class SortOptions(TextChoices):
        PERSON = 'person', _l('Person')
        ID = 'id', _l('Reference')
        AUTHORIZATION_TYPE = 'authorization_type', _l('Type')
        ACCOUNT_HOLDER_NAME = 'account_holder_name', _l('Account holder')
        IBAN = 'iban', _l('IBAN')
        BIC = 'bic', _l('BIC')
        START_DATE = 'start_date', _l('Starts on')
        END_DATE = 'end_date', _l('Ends on')

    search = forms.CharField(required=False, label=_l('Search'))
    status = forms.MultipleChoiceField(required=False, choices=AuthorizationStatuses.choices,
                                       widget=forms.CheckboxSelectMultiple, label=_l('Status'))
    authorization_type = forms.ModelMultipleChoiceField(required=False, queryset=AuthorizationType.objects.all(),
                                                        widget=forms.CheckboxSelectMultiple, label=_l('Sort'))
    sort_by = forms.ChoiceField(required=False, choices=SortOptions.choices, initial=SortOptions.PERSON.value,
                                label=_l('Sort by'))
    reverse = forms.BooleanField(required=False, initial=False, label=_l('Sort in reverse'))


class RFIDCardForm(forms.ModelForm):
    def __init__(self, person, *args, **kwargs):
        super(RFIDCardForm, self).__init__(*args, **kwargs)
        self.fields['person'].initial = person
        self.fields['person'].widget = forms.HiddenInput()
        self.fields['active'].initial = True
        self.fields['active'].widget = forms.HiddenInput()

    class Meta:
        model = RFIDCard
        fields = ['person', 'code', 'active']


class AuthorizationSelectForm(forms.Form):
    authorizations = forms.ModelMultipleChoiceField(queryset=Authorization.objects.all(),
                                                    widget=forms.CheckboxSelectMultiple, label=_l('Mandates'))

    def __init__(self, authorizations_queryset, *args, **kwargs):
        super(AuthorizationSelectForm, self).__init__(*args, **kwargs)
        self.fields['authorizations'].queryset = authorizations_queryset
        self.fields['authorizations'].initial = authorizations_queryset


class StatisticsForm(forms.Form):
    start_date = forms.SplitDateTimeField(label=_l('Beginning:'), widget=DateTimeSelector, required=True)
    end_date = forms.SplitDateTimeField(label=_l('End (till)'), widget=DateTimeSelector, required=True)
    checkboxes = forms.MultipleChoiceField(label=_l('Tables:'), widget=forms.CheckboxSelectMultiple(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['checkboxes'].choices = [(x[1], x[2]) for x in statistics.get_functions()]


class CookieCornerPersonSearchForm(forms.Form):
    person = forms.IntegerField(widget=MemberSelect(attrs={'autofocus': 'autofocus', 'placeholder': _l('Find person')}),
                                label=_l('Person'), error_messages={'required': _l('Choose a name from the suggestions.')})


inject_style(StatisticsForm)

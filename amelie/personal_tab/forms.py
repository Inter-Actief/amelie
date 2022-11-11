from django import forms
from django.conf import settings
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from localflavor.generic.forms import BICFormField, IBANFormField

from amelie.style.forms import inject_style
from amelie.personal_tab import statistics
from amelie.personal_tab.models import CustomTransaction, CookieCornerTransaction, RFIDCard, Reversal, AuthorizationType, \
    DebtCollectionBatch, Authorization
from amelie.tools.widgets import DateSelector, DateTimeSelector, MemberSelect


class CustomTransactionForm(forms.ModelForm):
    date = forms.SplitDateTimeField(label=_('Date'), widget=DateTimeSelector, initial=timezone.now)

    class Meta:
        model = CustomTransaction
        fields = ['date', 'price', 'description']


class CookieCornerTransactionForm(forms.ModelForm):
    date = forms.SplitDateTimeField(label=_('Date'), widget=DateTimeSelector, initial=timezone.now)

    class Meta:
        model = CookieCornerTransaction
        fields = ['date', 'price', 'description', 'article', 'amount']


class ExamCookieCreditForm(forms.Form):
    price = forms.DecimalField(max_digits=8, decimal_places=2, label=_('Price'))
    description = forms.CharField(max_length=200, label=_('Description'))


class DebtCollectionForm(forms.Form):
    description = forms.CharField(max_length=50, label=_('Description for within Inter-Actief'))
    execution_date = forms.DateField(label=_('Date of execution'), widget=DateSelector)
    contribution = forms.BooleanField(required=False, label=_('Membership fee'))
    cookie_corner = forms.BooleanField(required=False, label=_('Personal tab'))
    end = forms.SplitDateTimeField(label=_('Transactions until'), widget=DateTimeSelector)

    def __init__(self, minimal_execution_date, *args, **kwargs):
        super(DebtCollectionForm, self).__init__(*args, **kwargs)
        self.minimal_execution_date = minimal_execution_date
        self.fields['execution_date'].initial = minimal_execution_date

    def clean_execution_date(self):
        data = self.cleaned_data['execution_date']
        if data < self.minimal_execution_date:
            raise forms.ValidationError(_('Date of execution is too soon'))
        if data.weekday() >= 5:  # Saturday or sunday
            raise forms.ValidationError(_('Date of execution cannot be during the weekend'))

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
    date = forms.DateField(label=_('Date'))

    """IBAN for authorization"""
    iban = IBANFormField(label=_('IBAN'))

    """BIC for authorization"""
    bic = BICFormField(label=_('BIC*'), required=False)

    """Short description of the reason of this amendment."""
    reason = forms.CharField(max_length=250, label=_('Remarks'),
                             help_text=_('Short description of the reason for the amendment'))

    def clean(self):
        cleaned_data = super(AmendmentForm, self).clean()
        if self.errors:
            # Skips checks if errors are found.
            return cleaned_data

        if not cleaned_data['bic']:
            if not cleaned_data['iban'][:2] == 'NL':
                self.add_error('bic', _('BIC has to be entered for foreign bank accounts.'))
            elif cleaned_data['iban'][4:8] in settings.COOKIE_CORNER_BANK_CODES:
                cleaned_data['bic'] = settings.COOKIE_CORNER_BANK_CODES[cleaned_data['iban'][4:8]]
            else:
                self.add_error('bic', _('BIC could not be generated, please enter yourself.'))
        return cleaned_data


inject_style(CustomTransactionForm, CookieCornerTransactionForm, ExamCookieCreditForm, DebtCollectionForm, ReversalForm,
             AmendmentForm)


class SearchAuthorizationForm(forms.Form):
    class AuthorizationStatuses(TextChoices):
        UNSIGNED = 'unsigned', _("Not signed")
        ACTIVE = 'active', _("Active")
        TERMINATED = 'terminated', _("Ended")

    class SortOptions(TextChoices):
        PERSON = 'person', _('Person')
        ID = 'id', _('Reference')
        AUTHORIZATION_TYPE = 'authorization_type', _('Type')
        ACCOUNT_HOLDER_NAME = 'account_holder_name', _('Account holder')
        IBAN = 'iban', _('IBAN')
        BIC = 'bic', _('BIC')
        START_DATE = 'start_date', _('Starts on')
        END_DATE = 'end_date', _('Ends on')

    search = forms.CharField(required=False, label=_('Search'))
    status = forms.MultipleChoiceField(required=False, choices=AuthorizationStatuses.choices,
                                       widget=forms.CheckboxSelectMultiple, label=_('Status'))
    authorization_type = forms.ModelMultipleChoiceField(required=False, queryset=AuthorizationType.objects.all(),
                                                        widget=forms.CheckboxSelectMultiple, label=_('Sort'))
    sort_by = forms.ChoiceField(required=False, choices=SortOptions.choices, initial=SortOptions.PERSON.value,
                                label=_('Sort by'))
    reverse = forms.BooleanField(required=False, initial=False, label=_('Sort in reverse'))


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
                                                    widget=forms.CheckboxSelectMultiple, label=_('Mandates'))

    def __init__(self, authorizations_queryset, *args, **kwargs):
        super(AuthorizationSelectForm, self).__init__(*args, **kwargs)
        self.fields['authorizations'].queryset = authorizations_queryset
        self.fields['authorizations'].initial = authorizations_queryset


class StatisticsForm(forms.Form):
    start_date = forms.SplitDateTimeField(label=_('Beginning:'), widget=DateTimeSelector, required=True)
    end_date = forms.SplitDateTimeField(label=_('End (till)'), widget=DateTimeSelector, required=True)
    checkboxes = forms.MultipleChoiceField(label=_('Tables:'), widget=forms.CheckboxSelectMultiple(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['checkboxes'].choices = [(x[1], x[2]) for x in statistics.get_functions()]


class CookieCornerPersonSearchForm(forms.Form):
    person = forms.IntegerField(widget=MemberSelect(attrs={'autofocus': 'autofocus', 'placeholder': _('Find person')}),
                                label=_('Person'), error_messages={'required': _('Choose a name from the suggestions.')})


inject_style(StatisticsForm)

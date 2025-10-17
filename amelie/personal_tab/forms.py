import logging
import math
import traceback
from decimal import Decimal
from localflavor.generic.forms import BICFormField, IBANFormField

from django import forms
from django.conf import settings
from django.db import transaction
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l

from amelie.members.models import Person, Committee
from amelie.personal_tab.transactions import cookie_corner_sale
from amelie.style.forms import inject_style
from amelie.personal_tab import statistics
from amelie.personal_tab.models import CustomTransaction, CookieCornerTransaction, RFIDCard, Reversal, AuthorizationType, \
    DebtCollectionBatch, Authorization
from amelie.tools.http import get_client_ips
from amelie.tools.ipp_printer import IPPPrinter
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


def get_printer_choices():
    return [
        (k, p['name'])
        for k, p in settings.PERSONAL_TAB_PRINTERS.items()
    ]


class PrintDocumentForm(forms.Form):
    document = forms.FileField(
        label=_l('PDF Document'),
        help_text=_l('Select a PDF document to print'),
        widget=forms.FileInput(attrs={'accept': '.pdf'})
    )
    printer = forms.ChoiceField(
        label=_l('Printer'),
        choices=get_printer_choices,
        help_text=_l('Select the printer to use for printing')
    )
    committee = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        empty_label=_l("-- Pay via personal tab --"),
        required=False,
        label=_l('Committee'),
        help_text=_l('Select a committee for free printing, or leave blank to pay for printing')
    )
    copies = forms.IntegerField(
        initial=1,
        label=_l('Copies'),
        help_text=_l('Number of copies to print'),
        min_value=1, max_value=25
    )
    dual_sided = forms.BooleanField(
        required=False,
        initial=True,
        label=_l('Dual-sided printing'),
        help_text=_l('Print both sides of the page. Leave unchecked for single-sided printing.')
    )

    def __init__(self, person: Person, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show committees that the person is a member of
        self.fields['committee'].queryset = person.current_committees()
        self.person = person

    def clean_document(self):
        document = self.cleaned_data.get('document')

        if not document:
            raise forms.ValidationError(_l('Please select a PDF file.'))

        # Check file extension
        if not document.name.lower().endswith('.pdf'):
            raise forms.ValidationError(_l('Only PDF files are allowed.'))

        # Check file size (limit to 50MB)
        max_size = settings.PERSONAL_TAB_PRINTER_MAX_FILE_SIZE
        if document.size > max_size:
            raise forms.ValidationError(_l('File size cannot exceed 50MB.'))

        return document

    def clean(self):
        self.cleaned_data = super().clean()
        committee: Committee = self.cleaned_data.get('committee')

        # Check if the user is allowed to print this request
        if committee and not self.person.is_in_committee(committee.abbreviation):
            raise forms.ValidationError(
                _l('You are not a member of the committee you want to print for.')
            )
        elif not committee and not (self.person.has_mandate_consumptions() and self.person.is_member()):
            raise forms.ValidationError(
                _l('You do not have an active consumption mandate or are not a member anymore, '
                   'so we cannot add the costs for this print to your personal tab. Contact the board for help.')
            )

        return self.cleaned_data

    def save(self, request):
        """
        Process the form and create necessary database entries.
        """
        from amelie.personal_tab.models import PrintLogEntry, Article

        document = self.cleaned_data['document']
        committee = self.cleaned_data.get('committee')
        printer_key = self.cleaned_data['printer']
        num_copies = self.cleaned_data['copies']
        dual_sided = self.cleaned_data.get('dual_sided')

        # Get page count from PDF
        import pypdf
        reader = pypdf.PdfReader(document)
        page_count = reader.get_num_pages()

        # Page count is halved (ceiled) when printing dual-sided
        if dual_sided:
            page_count = math.ceil(page_count / 2)

        # Page count is multiplied when printing multiple copies
        page_count *= num_copies

        # Get client IP and user agent
        all_ips, real_ip = get_client_ips(request)
        source_useragent = request.META.get('HTTP_USER_AGENT', '')[:255]

        with transaction.atomic():
            # Create the print log entry
            print_log = PrintLogEntry.objects.create(
                actor=request.user.person,
                document_name=document.name,
                page_count=page_count,
                committee=committee,
                source_ip=real_ip,
                source_useragent=source_useragent
            )

            # If no committee selected, create a transaction for payment
            if not committee:
                try:
                    # Get the printing article (ID configured in settings)
                    article = Article.objects.get(id=settings.PERSONAL_TAB_PRINTER_PAGE_ARTICLE_ID)

                    # Create cookie corner transaction for the pages
                    cookie_transaction = cookie_corner_sale(article=article, amount=page_count,
                                                            person=request.user.person, added_by=request.user.person)

                    # Link the transaction to the print log
                    print_log.transaction = cookie_transaction
                    print_log.save()

                except Article.DoesNotExist:
                    raise forms.ValidationError(_l('Printing article not found. Please contact support.'))

            # Print the document
            try:
                printer = IPPPrinter(printer_key=printer_key)
                printer.print_document(
                    document=document,
                    job_name=f"Amelie #{print_log.id} - {print_log.actor}",
                    num_copies=num_copies, dual_sided=dual_sided
                )
                logging.info(f"Print job submitted: {document.name} ({print_log.page_count} pages) "
                            f"for user {print_log.actor} (Print Log ID: {print_log.id})")
            except Exception as e:
                trace = traceback.format_exc()
                logging.error(f"Error while printing document: {e} - {trace}")
                raise e

            return print_log


inject_style(StatisticsForm, PrintDocumentForm)

# coding=utf-8
import csv
import datetime
import logging
from decimal import Decimal
import itertools

import django.conf
import operator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse, reverse_lazy
from django.utils.translation import get_language
from django.db import transaction
from django.db.models import Sum, Q, Count, Aggregate
from django.db.models.functions import TruncDay
from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import formats, timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, get_language
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView, DeleteView
from django.views.generic.edit import FormView
from functools import reduce

from amelie.calendar.models import Event
from amelie.members.models import Person, Membership
from amelie.members.query_forms import MailingForm
from amelie.settings.generic import DATE_PRE_SEPA_AUTHORIZATIONS
from amelie.personal_tab.alexia import get_alexia, parse_datetime
from amelie.personal_tab.helpers import kcal_equivalent
from amelie.personal_tab.forms import CookieCornerTransactionForm, CustomTransactionForm, ExamCookieCreditForm, \
    DebtCollectionForm, ReversalForm, SearchAuthorizationForm, AmendmentForm, DebtCollectionBatchForm, \
    AuthorizationSelectForm, \
    StatisticsForm, PersonSpendingLimitsForm
from amelie.personal_tab.debt_collection import generate_contribution_instructions, filter_contribution_instructions, \
    save_contribution_instructions, generate_cookie_corner_instructions, filter_cookie_corner_instructions, save_cookie_corner_instructions, \
    process_reversal, process_amendment
from amelie.personal_tab.models import Category, Transaction, CookieCornerTransaction, ActivityTransaction, \
    CustomTransaction, AlexiaTransaction, RFIDCard, Authorization, DebtCollectionAssignment, DebtCollectionBatch, DiscountCredit, \
    DebtCollectionInstruction, ReversalTransaction
from amelie.personal_tab.statistics import get_functions, statistics_totals
from amelie.personal_tab.transactions import exam_cookie_discount, \
    exam_cookie_credit as transactions_exam_cookie_credit, add_exam_cookie_credit
from amelie.tools.decorators import require_lid, require_board, require_ajax
from amelie.tools.forms import PeriodTimeForm, DateTimeForm, ExportForm
from amelie.tools.logic import current_association_year
from amelie.tools.mixins import RequirePersonMixin, RequireBoardMixin

DATETIMEFORMAT = '%Y%m%d%H%M%S'

logger = logging.getLogger(__name__)


def _urlize(dt):
    """
    Convert datetime to url format
    """
    return dt.astimezone(timezone.utc).strftime(DATETIMEFORMAT)


def _parsedatetime(inputstr):
    if isinstance(inputstr, int):
        inputstr = str(inputstr)
    return datetime.datetime.strptime(inputstr, DATETIMEFORMAT).replace(tzinfo=timezone.utc)


@require_lid
def overview(request):
    # Redirect to personal overview if the person is not a board member.
    if not request.is_board:
        return HttpResponseRedirect(reverse('personal_tab:dashboard', args=(request.person.pk, request.person.slug)))

    return render(request, 'cookie_corner_overview.html', locals())


@require_lid
def price_list(request):
    categories_queryset = Category.objects.filter(is_available=True)
    if get_language() == 'en':
        categories_queryset = categories_queryset.order_by('order', 'name_en')

    categories = []
    for category_obj in categories_queryset:
        category = {'id': category_obj.id, 'name': category_obj.name}
        articles_queryset = category_obj.article_set.filter(is_available=True)

        if get_language() == 'en':
            articles_queryset = articles_queryset.order_by('name_en')

        articles = []
        for article in articles_queryset:
            kcal_per_euro = article.kcal // article.price if article.kcal is not None and article.price else None
            articles.append({'article': article, 'kcal_per_euro': kcal_per_euro})
        category.update({'articles': articles})
        categories.append(category)

    return render(request, 'price_list.html', {'categories': categories})


def generate_overview_new(request, person, date_from=None, date_to=None):
    """
    New method to generate a transaction overview based on DateTimes instead of Dates.
    """
    view_name = request.resolver_match.view_name

    localtz = timezone.get_current_timezone()

    start_url = _urlize(date_from) if date_from else None
    end_url = _urlize(date_to) if date_to else None

    transaction_types = [CookieCornerTransaction, ActivityTransaction, AlexiaTransaction, CustomTransaction]
    transaction_filter = []
    if date_from or date_to:
        transaction_filter.append(Q(date__gte=date_from, date__lt=date_to))

    # Filter on Person
    if person is not None:
        transaction_filter.append(Q(person=person))

    _trans = Transaction.objects.all()
    if transaction_filter:
        _trans = _trans.filter(reduce(operator.and_, transaction_filter))

    has_transactions = _trans.exists()

    # Vars for template context that might not be initialized sometimes
    overview_type = None
    total = False
    totals = None
    kcal_totals = None
    all_transactions = None
    rows = None

    if has_transactions:
        first = _trans.order_by('date')[0]
        last = _trans.order_by('-date')[0]
        difference = last.date - first.date

        # Totals are dependent on the type of overview
        if difference.days >= 400:
            overview_type = 'total'
        elif difference.days >= 35:
            overview_type = 'year'
        elif difference.days >= 1:
            overview_type = 'month'
        else:
            total = True  # Generate totals
            overview_type = 'day'

        # Execute query
        if len(transaction_filter) > 0:
            all_transactions = [x.objects.filter(reduce(operator.and_, transaction_filter)) for x in transaction_types]
        else:
            all_transactions = [x.objects.all() for x in transaction_types]

        if overview_type == 'day':
            all_transactions[0] = all_transactions[0].select_related('person', 'article', 'discount')
            all_transactions[1] = all_transactions[1].select_related('person', 'event')
            all_transactions[2] = all_transactions[2].select_related('person')
            all_transactions[3] = all_transactions[3].select_related('person')

        # On total page show the latest 10 transactions
        # TODO: variable does not seem to be used? - albertskja 26-04-2018
        if not date_from:
            # Table with latest 10 transactions
            latest_10_transactions = _trans.order_by('-added_on')[:10]

        # Generate table with data
        if overview_type != 'day':
            data = set()
            rows = []

            if overview_type == 'total':
                def _datetime_start(t):
                    return datetime.datetime(t.year, 1, 1).replace(tzinfo=localtz)

                def _datetime_end(t):
                    return datetime.datetime(t.year + 1, 1, 1).replace(tzinfo=localtz)

            elif overview_type == 'year':
                def _datetime_start(t):
                    return datetime.datetime(t.year, t.month, 1).replace(tzinfo=localtz)

                def _datetime_end(t):
                    if t.month < 12:
                        return datetime.datetime(t.year, t.month + 1, 1).replace(tzinfo=localtz)
                    else:
                        return datetime.datetime(t.year + 1, 1, 1).replace(tzinfo=localtz)

            elif overview_type == 'month':
                def _datetime_start(t):
                    return datetime.datetime(t.year, t.month, t.day).replace(tzinfo=localtz)

                def _datetime_end(t):
                    t2 = t + datetime.timedelta(days=1)
                    return datetime.datetime(t2.year, t2.month, t2.day).replace(tzinfo=localtz)
            else:
                raise ValueError

            for trans in itertools.chain.from_iterable(all_transactions):
                data.add(_datetime_start(trans.date.astimezone(localtz)))

            for date in sorted(data):
                amounts = [
                    x.filter(date__gte=date, date__lt=_datetime_end(date)).aggregate(Sum('price'))['price__sum'] or 0
                    for x in all_transactions]

                # Add the total to the end
                amounts.append(sum(amounts))

                # TODO: BLEGH, custom SQL! - albertskja 2018-04-25
                kcal_total = all_transactions[0].select_related('article').filter(
                    date__gte=date,
                    date__lt=_datetime_end(date)).extra(
                        select={
                            'kcal_total': "SUM(`personal_tab_article`.`kcal` * `personal_tab_cookiecornertransaction`.`amount`)"
                        }).values('kcal_total', 'article__kcal')[0]['kcal_total'] or 0

                start_url_d = max(_urlize(date), start_url) if start_url else _urlize(date)
                end_url_d = min(_urlize(_datetime_end(date)), end_url) if end_url else _urlize(_datetime_end(date))

                rows.append({
                    'date': date,
                    'amounts': amounts,
                    'kcal_total': kcal_total,
                    'start_url': start_url_d,
                    'end_url': end_url_d
                })

        # Calculate totals
        totals = [x.aggregate(Sum('price'))['price__sum'] or 0 for x in all_transactions]

        # Add totals to the end
        totals.append(sum(totals))

        # TODO: BLEGH, custom SQL! - albertskja 2018-04-25
        kcal_totals = all_transactions[0].select_related('article').extra(
            select={
                'kcal_total': "SUM(`personal_tab_article`.`kcal` * `personal_tab_cookiecornertransaction`.`amount`)"
            }).values('kcal_total', 'article__kcal')[0]['kcal_total'] or 0

    # Form shite
    form = PeriodTimeForm(initial={'datetime_from': date_from, 'datetime_to': date_to})

    # Done!
    return render(request, 'cookie_corner_transactions_new.html', {
        'person': person,
        'form': form,
        'date_from': date_from,
        'date_to': date_to,
        'has_transactions': has_transactions,
        'all_transactions': all_transactions,
        'overview_type': overview_type,
        'total': total,
        'totals': totals,
        'kcal_totals': kcal_totals,
        'rows': rows,
        'view_name': view_name
    })


def generate_overview_exam_cookie_credit(request, person, date_from=None, date_to=None):
    """
    Generate transaction overview for exam cookie credit.
    """
    view_name = request.resolver_match.view_name

    localtz = timezone.get_current_timezone()

    start_url = _urlize(date_from) if date_from else None
    end_url = _urlize(date_to) if date_to else None

    discount_period = exam_cookie_discount()

    _exam_cookie_credits = DiscountCredit.objects.filter(discount_period=discount_period)
    type_transactions = [_exam_cookie_credits, _exam_cookie_credits.filter(discount__isnull=True),
                         _exam_cookie_credits.filter(discount__isnull=False)]
    transaction_filter = []
    if date_from:
        transaction_filter.append(Q(date__gte=date_from, date__lt=date_to))
    if date_to:
        transaction_filter.append(Q(date__gte=date_from, date__lt=date_to))

    # Filter on person
    if person is not None:
        transaction_filter.append(Q(person=person))

    _trans = type_transactions[0]
    if transaction_filter:
        _trans = _trans.filter(reduce(operator.and_, transaction_filter))

    has_transactions = _trans.exists()

    # Vars for template context that might not be initialized sometimes
    overview_type = None
    all_transactions = None
    total = False
    totals = None
    last_10_transactions = None
    rows = None

    if has_transactions:
        first = _trans.order_by('date')[0]
        last = _trans.order_by('-date')[0]

        diff = last.date - first.date

        # Totals are dependent on the type of overview
        if diff.days >= 400:
            table = 'year'
            overview_type = 'total'
        elif diff.days >= 35:
            table = 'month'
            overview_type = 'year'
        elif diff.days >= 1:
            table = 'day'
            overview_type = 'month'
        else:
            total = True  # Generate totals
            overview_type = 'day'

        # Execute query
        if len(transaction_filter) > 0:
            all_transactions = [x.filter(reduce(operator.and_, transaction_filter)) for x in type_transactions]
        else:
            all_transactions = [x.all() for x in type_transactions]

        if overview_type == 'day':
            all_transactions[0] = all_transactions[0].select_related('person')
            all_transactions[1] = all_transactions[1].select_related('person')
            all_transactions[2] = all_transactions[2].select_related('person')

        # Show last 10 transactions on totals page
        if not date_from:
            last_10_transactions = all_transactions[0].order_by('-added_on')[:10]

        # Generate table with data
        if overview_type != 'day':
            data = set()
            rows = []

            if overview_type == 'total':
                def _datetime_start(t):
                    return datetime.datetime(t.year, 1, 1).replace(tzinfo=localtz)

                def _datetime_end(t):
                    return datetime.datetime(t.year + 1, 1, 1).replace(tzinfo=localtz)

            elif overview_type == 'year':
                def _datetime_start(t):
                    return datetime.datetime(t.year, t.month, 1).replace(tzinfo=localtz)

                def _datetime_end(t):
                    if t.month < 12:
                        return datetime.datetime(t.year, t.month + 1, 1).replace(tzinfo=localtz)
                    else:
                        return datetime.datetime(t.year + 1, 1, 1).replace(tzinfo=localtz)

            elif overview_type == 'month':
                def _datetime_start(t):
                    return datetime.datetime(t.year, t.month, t.day).replace(tzinfo=localtz)

                def _datetime_end(t):
                    t2 = t + datetime.timedelta(days=1)
                    return datetime.datetime(t2.year, t2.month, t2.day).replace(tzinfo=localtz)

            else:
                raise ValueError

            for trans in all_transactions[0]:
                data.add(_datetime_start(trans.date.astimezone(localtz)))

            data = sorted(list(data))

            for date in data:
                amounts = [
                    x.filter(date__gte=date, date__lt=_datetime_end(date)).aggregate(Sum('price'))['price__sum'] or 0
                    for x in all_transactions]

                start_url_d = max(_urlize(date), start_url) if start_url else _urlize(date)
                end_url_d = min(_urlize(_datetime_end(date)), end_url) if end_url else _urlize(_datetime_end(date))

                rows.append({
                    'date': date,
                    'amounts': amounts,
                    'start_url': start_url_d,
                    'end_url': end_url_d
                })

        # Calculate totals
        totals = [x.aggregate(Sum('price'))['price__sum'] or 0 for x in all_transactions]

    # Form shite
    form = PeriodTimeForm(initial={'datetime_from': date_from, 'datetime_to': date_to})

    # Done!
    return render(request, 'cookie_corner_exam_cookie_credit.html', {
        'view_name': view_name,
        'form': form,
        'person': person,
        'has_transactions': has_transactions,
        'overview_type': overview_type,
        'all_transactions': all_transactions,
        'total': total,
        'totals': totals,
        'date_from': date_from,
        'date_to': date_to,
        'last_10_transactions': last_10_transactions,
        'rows': rows
    })


@require_ajax
@require_lid
def rfid_change_status(request, rfid_id, status):
    rfid = get_object_or_404(RFIDCard, pk=rfid_id)
    person = rfid.person

    # Only the person themselves or the board has access to this.
    if not request.person.pk == person.pk and not request.is_board:
        return HttpResponseForbidden()

    # Change the status
    rfid.active = status == 'activate'
    rfid.save()

    # Get new set of cards for template
    rfids = person.rfidcard_set.all()

    # Done!
    return render(request, 'info/rfid_cards.html', {'rfids': rfids})


@require_ajax
@require_lid
def rfid_remove(request, rfid_id):
    rfid = get_object_or_404(RFIDCard, pk=rfid_id)
    person = rfid.person

    # Only the person themselves or the board has access to this.
    if not request.person == person and not request.is_board:
        return HttpResponseForbidden()

    # Delete the card
    rfid.delete()

    # Get new set of cards for template
    rfids = person.rfidcard_set.all()

    # Done!
    return render(request, 'info/rfid_cards.html', {'rfids': rfids})


@require_board
def transaction_overview(request, date_from=False, date_to=False):
    """Give an overview of transactions."""

    # Redirect to a page based on POST (handy for linking)
    if request.method == 'POST':
        form = PeriodTimeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['datetime_from'].astimezone(timezone.utc)
            end = form.cleaned_data['datetime_to'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:transactions', args=[_urlize(start), _urlize(end)]))

    if not date_from:
        # No period given
        return generate_overview_new(request, None)

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date`'))
    return generate_overview_new(request, None, start, end)


class TransactionSecurityMixin(RequirePersonMixin):
    """
    Mixin for SingleObjectMixin and MultipleObjectMixin to select only transactions
    the current user is allowed to see.
    """

    def get_queryset(self):
        queryset = super(TransactionSecurityMixin, self).get_queryset()
        if not self.request.is_board:
            queryset = queryset.filter(person=self.request.person)
        return queryset


class ActivityTransactionDetail(TransactionSecurityMixin, DetailView):
    model = ActivityTransaction
    template_name = 'cookie_corner/activity_transaction_detail.html'


class AlexiaTransactionDetail(TransactionSecurityMixin, DetailView):
    model = AlexiaTransaction
    template_name = 'cookie_corner/alexia_transaction_detail.html'

    def get_context_data(self, **kwargs):
        context = super(AlexiaTransactionDetail, self).get_context_data(**kwargs)

        transaction_id = self.get_object().transaction_id

        try:
            server = get_alexia()
            alexia_info = server.order.get(transaction_id)

            # Convert placed_at to datetime
            alexia_info['placed_at'] = parse_datetime(alexia_info['placed_at'])
            context['alexia'] = alexia_info

            # Calculate the total amount
            context['total'] = sum([Decimal(purchase['price']) for purchase in alexia_info['purchases']])
        except Exception as e:
            logger.exception('Getting order data from Alexia failed. Error: {}'.format(e))

        return context


class CookieCornerTransactionDetail(TransactionSecurityMixin, DetailView):
    model = CookieCornerTransaction
    template_name = 'cookie_corner/cookie_corner_transaction_detail.html'


class ReversalTransactionDetail(TransactionSecurityMixin, DetailView):
    model = ReversalTransaction
    template_name = 'cookie_corner/reversal_transaction_detail.html'


class TransactionDetail(TransactionSecurityMixin, DetailView):
    model = Transaction
    template_name = 'cookie_corner/transaction_detail.html'

    def get(self, request, *args, **kwargs):
        obj = self.get_object()

        # Redirect to more specific detail view if available
        if hasattr(obj, 'activitytransaction') and obj.activitytransaction:
            return redirect(obj.activitytransaction.get_absolute_url())
        elif hasattr(obj, 'alexiatransaction') and obj.alexiatransaction:
            return redirect(obj.alexiatransaction.get_absolute_url())
        elif hasattr(obj, 'cookiecornertransaction') and obj.cookiecornertransaction:
            return redirect(obj.cookiecornertransaction.get_absolute_url())
        elif hasattr(obj, 'reversaltransaction') and obj.reversaltransaction:
            return redirect(obj.reversaltransaction.get_absolute_url())

        return super(TransactionDetail, self).get(request, *args, **kwargs)


class CustomTransactionUpdate(RequireBoardMixin, UpdateView):
    model = CustomTransaction
    form_class = CustomTransactionForm
    template_name = 'cookie_corner/transaction_form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj or not obj.editable:
            raise Http404(_('Transaction not editable.'))

        return super(CustomTransactionUpdate, self).dispatch(request, *args, **kwargs)


class CookieCornerTransactionUpdate(CustomTransactionUpdate):
    model = CookieCornerTransaction
    form_class = CookieCornerTransactionForm


class CustomTransactionDelete(RequireBoardMixin, DeleteView):
    model = CustomTransaction
    template_name = 'cookie_corner/transaction_delete.html'

    def get_success_url(self):
        return reverse('personal_tab:dashboard', kwargs={'pk': self.object.person.pk, 'slug': self.object.person.slug})

    def delete(self, request, *args, **kwargs):
        delete = super(CustomTransactionDelete, self).delete(request, *args, **kwargs)
        messages.success(request, _("The transaction '{transaction}' has been successfully deleted.")
                         .format(transaction=self.object))
        return delete

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj or not obj.editable:
            raise Http404(_('Transaction not deletable.'))

        return super(CustomTransactionDelete, self).dispatch(request, *args, **kwargs)


class CookieCornerTransactionDelete(CustomTransactionDelete):
    model = CookieCornerTransaction


@require_lid
def dashboard(request, pk, slug):
    """Cookie corner dashboard."""
    person = get_object_or_404(Person, pk=pk, slug=slug)

    # Only the person themselves or the board has access to this.
    if not request.person == person and not request.is_board:
        return HttpResponseForbidden()

    personal_transactions = Transaction.objects.filter(person=person).order_by('-added_on')[:5]

    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    begin = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=timezone.utc)
    now = timezone.now()
    today = now.astimezone(timezone.get_default_timezone()).date()

    curr_balance = Transaction.objects.filter(person=person, date__gte=begin, date__lt=now).aggregate(
        Sum('price'))['price__sum'] or Decimal('0.00')
    all_balance = Transaction.objects.filter(person=person, date__gte=begin).aggregate(
        Sum('price'))['price__sum'] or Decimal('0.00')

    future_debt_collection_instructions = DebtCollectionInstruction.objects.filter(authorization__person=person,
                                                                                   batch__execution_date__gt=today)

    exam_cookie_credits = transactions_exam_cookie_credit(person)
    debt_collection_instructions = DebtCollectionInstruction.objects.filter(authorization__person=person
                                                                            ).order_by('-batch__execution_date')[:5]

    # Date on which the old (pre-SEPA) authorizations are registered
    date_old_authorizations = DATE_PRE_SEPA_AUTHORIZATIONS

    return render(request, 'cookie_corner_dashboard.html', {
        'person': person,
        'transactions': personal_transactions,
        'curr_balance': curr_balance,
        'all_balance': all_balance,
        'future_debt_collection_instructions': future_debt_collection_instructions,
        'debt_collection_instructions': debt_collection_instructions,
        'exam_cookie_credits': exam_cookie_credits,
        'date_old_authorizations': date_old_authorizations,
        'wrapped_year': django.conf.settings.COOKIE_CORNER_WRAPPED_YEAR
    })


@require_lid
def my_dashboard(request):
    """
    Legacy redirect to personal dashboard.
    """
    return redirect('personal_tab:dashboard', pk=request.person.pk, slug=request.person.slug)


@require_lid
def person_transactions(request, pk, slug, date_from=None, date_to=None):
    person = get_object_or_404(Person, pk=pk, slug=slug)

    # Only the person themselves or the board has access to this.
    if not request.person == person and not request.is_board:
        return HttpResponseForbidden()

    # Redirect to a page based on POST (handy for links)
    if request.method == 'POST':
        form = PeriodTimeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['datetime_from'].astimezone(timezone.utc)
            end = form.cleaned_data['datetime_to'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:person_transactions', kwargs={
                'pk': pk, 'slug': slug, 'date_from': _urlize(start), 'date_to': _urlize(end)
            }))

    if not date_from:
        # No period given
        return generate_overview_new(request, person)

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date'))

    return generate_overview_new(request, person, start, end)


@require_board
def person_new_transaction(request, person_id, slug, transaction_type):
    person = get_object_or_404(Person, id=person_id, slug=slug)
    transaction_type = transaction_type.lower()

    if transaction_type == 'cookie_corner':
        form = CookieCornerTransactionForm(data=request.POST or None)
    elif transaction_type == 'other':
        form = CustomTransactionForm(data=request.POST or None)
    else:
        raise Http404()

    if request.method == 'POST':
        if form.is_valid():
            form.instance.person = person
            form.instance.added_by = request.person
            form.save()

            return HttpResponseRedirect(reverse('personal_tab:dashboard', args=[person.pk, person.slug]))

    # Done!
    return render(request, 'cookie_corner/transaction_form.html', {
        'transaction_type': transaction_type,
        'form': form
    })


@login_required
def person_debt_collection_instructions(request, person_id, slug):
    person = get_object_or_404(Person, id=person_id, slug=slug)
    debt_collection_instructions = DebtCollectionInstruction.objects.filter(authorization__person=person)

    # Done
    return render(request, 'cookie_corner_person_debt_collection_instructions.html', {
        'person': person,
        'debt_collection_instructions': debt_collection_instructions
    })


@require_board
def exam_cookie_credit(request, date_from=False, date_to=False):
    """Give an overview of exam cookie credits."""

    # Redirect to a page based on POST (handy for links)
    if request.method == 'POST':
        form = PeriodTimeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['datetime_from'].astimezone(timezone.utc)
            end = form.cleaned_data['datetime_to'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:exam_cookie_credit',
                                                args=[_urlize(start), _urlize(end)]))

    if not date_from:
        # No period given
        return generate_overview_exam_cookie_credit(request, None)

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date`'))
    return generate_overview_exam_cookie_credit(request, None, start, end)


@require_lid
def person_exam_cookie_credit(request, person_id, slug, date_from=None, date_to=None):
    person = get_object_or_404(Person, id=person_id, slug=slug)

    # Only the person themselves or the board has access to this.
    if not request.person == person and not request.is_board:
        return HttpResponseForbidden()

    # Redirect to a page based on POST (handy for links)
    if request.method == 'POST':
        form = PeriodTimeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['datetime_from'].astimezone(timezone.utc)
            end = form.cleaned_data['datetime_to'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:person_exam_cookie_credit', kwargs={
                'person_id': person_id, 'slug': slug, 'date_from': _urlize(start), 'date_to': _urlize(end)
            }))

    if not date_from:
        # No period given
        return generate_overview_exam_cookie_credit(request, person)

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date`'))
    return generate_overview_exam_cookie_credit(request, person, start, end)


@require_board
def person_exam_cookie_credit_new(request, person_id, slug):
    person = get_object_or_404(Person, id=person_id, slug=slug)

    form = ExamCookieCreditForm(data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            price = form.cleaned_data['price']
            description = form.cleaned_data['description']
            added_by = request.person
            add_exam_cookie_credit(price, person, description, added_by)

            return HttpResponseRedirect(reverse('personal_tab:dashboard', args=[person.pk, person.slug]))

    # Done
    return render(request, 'cookie_corner_exam_cookie_credit_add.html', {
        'person': person,
        'form': form
    })


class PersonSpendingLimits(RequirePersonMixin, UpdateView):
    model = Person
    form_class = PersonSpendingLimitsForm
    template_name = 'cookie_corner_spending_limits.html'

    def get_success_url(self):
        return reverse('personal_tab:dashboard', kwargs={'pk': self.object.pk, 'slug': self.object.slug})


@require_board
def statistics_form(request):
    if request.method == 'POST':
        form = StatisticsForm(data=request.POST)
        if form.is_valid():
            start = form.cleaned_data['start_date'].astimezone(timezone.utc)
            end = form.cleaned_data['end_date'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:statistics', kwargs={
                'date_from': _urlize(start),
                'date_to': _urlize(end),
                'checkboxes': '-'.join(form.cleaned_data['checkboxes'])}))
        else:
            return render(request, 'cookie_corner_statistics_form.html', {'form': form})
    else:
        end_date = timezone.datetime(timezone.now().year, timezone.now().month, 1)
        begin_date = end_date - timezone.timedelta(days=1)
        begin_date = begin_date.replace(day=1)
        return render(request, 'cookie_corner_statistics_form.html', {
            'form': StatisticsForm(initial={
                'start_date': begin_date,
                'end_date': end_date,
                'checkboxes': [x[1] for x in get_functions() if x[3]]})
        })


@require_board
def statistics(request, date_from, date_to, checkboxes):
    functions = get_functions()
    names = {x[1]: x[2] for x in functions}

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
        choices = checkboxes.split('-')

        # Check all choices
        if not all(choice in names for choice in choices):
            raise Http404(_('Invalid statistics list'))

    except ValueError:
        raise Http404(_('Invalid date'))

    form = StatisticsForm(initial={'start_date': start, 'end_date': end, 'checkboxes': choices})

    # Get statistics
    tables = {}
    functions_dict = {x[1]: x[0] for x in functions}
    for option in choices:
        if option != 't':
            table = functions_dict[option](start, end)
            table['title'] = names[option]
            tables[option] = table

    if 't' in choices:
        tables['t'] = statistics_totals(start, end, tables)

    return render(request, 'cookie_corner_statistics.html', {
        'form': form, 'tables': tables, 'start': start, 'end': end,
        'total': 0, 'start_url': date_from, 'end_url': date_to
    })


@require_board
def balance(request, dt_str=False):

    # Redirect to a page based on GET (handy for links)
    if request.method == 'POST':
        form = DateTimeForm(request.POST)
        if form.is_valid():
            dt = form.cleaned_data['datetime'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:balance', args=[_urlize(dt)]))

    # Redirect to form if no date given
    if not dt_str:
        form = DateTimeForm()
        return render(request, 'cookie_corner_balance_form.html', {
            'form': form,
        })

    # Construct data
    try:
        dt = _parsedatetime(dt_str)
    except ValueError:
        raise Http404(_('Invalid date`'))
    form = DateTimeForm(initial={'datetime': dt})

    dt_url = _urlize(dt)

    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    begin = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=timezone.utc)

    all_transactions = Transaction.objects.filter(date__gte=begin, date__lt=dt)
    all_transactions_aggregated = all_transactions.aggregate(Sum('price'))
    all_transactions_sum = all_transactions_aggregated['price__sum']

    transaction_sum_per_person = all_transactions.values('person').order_by().annotate(Sum('price'))
    transaction_sum_per_person_dict = dict([(s['person'], s['price__sum']) for s in transaction_sum_per_person])

    persons = Person.objects.filter(pk__in=transaction_sum_per_person_dict.keys())

    person_totals = []

    for person in persons:
        if transaction_sum_per_person_dict[person.pk]:
            person_totals.append((person, transaction_sum_per_person_dict[person.pk]))

    # --- Exam cookie credit ---
    # Give activity statistics over a given period
    discount_period = exam_cookie_discount()
    exam_cookie_transactions = DiscountCredit.objects.filter(discount_period=discount_period, date__lt=dt)
    exam_cookie_sum = exam_cookie_transactions.aggregate(Sum('price'))['price__sum'] or 0

    exam_cookie_credit_per_person = exam_cookie_transactions.values('person').order_by().annotate(Sum('price'))
    exam_cookie_credit_per_person_dict = dict([(c['person'], c['price__sum']) for c in exam_cookie_credit_per_person])

    exam_cookie_persons = Person.objects.filter(pk__in=exam_cookie_credit_per_person_dict.keys())

    exam_cookie_person_totals = []

    for person in exam_cookie_persons:
        if exam_cookie_credit_per_person_dict[person.pk]:
            exam_cookie_person_totals.append((person, exam_cookie_credit_per_person_dict[person.pk]))

    return render(request, 'cookie_corner_balance_form.html', {
        'form': form,
        'all_transactions_sum': all_transactions_sum,
        'person_totals': person_totals,
        'exam_cookie_sum': exam_cookie_sum,
        'exam_cookie_person_totals': exam_cookie_person_totals,
        'dt': dt,
        'dt_url': dt_url
    })


@require_board
def export(request, date_from=False, date_to=False):
    """Export debt collection list over a certain period."""

    # TODO: Remove this export because it is not used any more and not compliant with GDPR.
    # Redirect to a page based on GET (handy for links)
    if request.method == 'POST':
        form = PeriodTimeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['datetime_from'].astimezone(timezone.utc)
            end = form.cleaned_data['datetime_to'].astimezone(timezone.utc)
            return HttpResponseRedirect(reverse('personal_tab:export', args=[_urlize(start), _urlize(end)]))

    # Redirect to form if no date given
    if not date_from:
        form = PeriodTimeForm()
        return render(request, 'cookie_corner_export_form.html', {
            'form': form
        })

    # Construct data
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date`'))
    form = PeriodTimeForm(initial={'datetime_from': start, 'datetime_to': end})

    start_url = _urlize(start)
    end_url = _urlize(end)

    # Filter transactions
    rows = export_filter(start, end)
    total = 0

    # Calculate totals
    for row in rows['good']:
        total += row['sum']

    # Done
    amount_rows = len(rows['good'])
    return render(request, 'cookie_corner_export_form.html', {
        'form': form,
        'start': start,
        'end': end,
        'start_url': start_url,
        'end_url': end_url,
        'rows': rows,
        'total': total,
        'amount_rows': amount_rows
    })


@require_board
def export_csv(request, date_from, date_to):
    try:
        start = _parsedatetime(date_from)
        end = _parsedatetime(date_to)
    except ValueError:
        raise Http404(_('Invalid date`'))
    rows = export_filter(start, end)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    # Use .txt. Excel 2007 forces the wrong character encoding (not UTF-8) with .csv
    response['Content-Disposition'] = 'attachment; filename=amelie-cookie-corner-%s-to-%s.txt' % (
        _urlize(start), _urlize(end))

    writer = csv.writer(response, dialect=csv.excel)
    writer.writerow(['Name', 'Amount', 'City', 'Payment reference', 'Description 2', 'Description 3', 'Description 4'])

    period = 'from ' + start.strftime("%Y-%m-%d") + ' to ' + end.strftime("%Y-%m-%d")

    for row in rows['good']:
        person = row['person']
        writer.writerow([mark_safe(str(person)), row['sumf'], person.city, 'Debt collection cookie corner', period,
               'For questions call 0534893756', ''])

    return response


def export_filter(begin, end):
    all_transactions = Transaction.objects.filter(date__gte=begin, date__lt=end)

    # Do not use order, so distinct works properly. See Django manual.
    persons = all_transactions.filter(person__isnull=False).order_by('person').distinct().values('person')
    result = {'good': [], 'negative': []}

    for p in persons:
        person = Person.objects.get(id=p['person'])
        if not person.has_mandate_consumptions():
            continue
        price = all_transactions.filter(person=person).aggregate(Sum('price'))['price__sum']
        rij = {'person': person, 'sum': price, 'sumf': ("%.2f" % price).replace('.', ',')}

        if price < 0:
            result['negative'].append(rij)
        elif price > 0:
            result['good'].append(rij)

    return result


@require_board
def activity_transactions(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    transactions = ActivityTransaction.objects.filter(event=event).select_related('person', 'event')

    # Calculate totals
    totals = transactions.aggregate(Sum('price'))['price__sum'] or 0

    # Done
    return render(request, 'cookie_corner_activity_transactions.html', {
        'event': event,
        'transactions': transactions,
        'totals': totals
    })


@require_board
def authorization_list(request):
    authorizations = Authorization.objects.all()

    form = SearchAuthorizationForm(request.GET)
    if form.is_valid():
        cleaned_data = form.cleaned_data

        if cleaned_data['search']:
            search = cleaned_data['search']
            authorizations = authorizations.filter(Q(id__icontains=search) | Q(person__first_name__icontains=search) | Q(
                person__last_name_prefix__icontains=search) | Q(person__last_name__icontains=search) | Q(
                iban__icontains=search) | Q(bic__icontains=search) | Q(account_holder_name__icontains=search))
        if cleaned_data['authorization_type']:
            authorizations = authorizations.filter(authorization_type__in=cleaned_data['authorization_type'])
        if cleaned_data['status']:
            if 'unsigned' not in cleaned_data['status']:
                authorizations = authorizations.filter(is_signed=True)
            if 'active' not in cleaned_data['status']:
                authorizations = authorizations.filter(Q(is_signed=False) | Q(end_date__isnull=False))
            if 'terminated' not in cleaned_data['status']:
                authorizations = authorizations.filter(end_date__isnull=True)
        if cleaned_data['sort_by']:
            if cleaned_data['reverse']:
                authorizations = authorizations.order_by('-%s' % cleaned_data['sort_by'])
            else:
                authorizations = authorizations.order_by(cleaned_data['sort_by'])

    authorizations = authorizations.select_related('authorization_type', 'person')

    get = request.GET.copy()
    if 'page' in get:
        del get['page']
    query = get.urlencode()

    paginator = Paginator(authorizations, 50)  # Show 100 contacts per page
    page = request.GET.get('page')
    try:
        authorizations = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        authorizations = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        authorizations = paginator.page(paginator.num_pages)

    # Date on which old (pre-SEPA) authorizations are registered
    date_old_authorizations = DATE_PRE_SEPA_AUTHORIZATIONS

    return render(request, 'cookie_corner_authorization_list.html', {
        'form': form,
        'authorizations': authorizations,
        'query': query,
        'date_old_authorizations': date_old_authorizations
    })


class AuthorizationTerminateView(RequireBoardMixin, FormView):
    """
    View to terminate active but unused mandates.
    """
    form_class = AuthorizationSelectForm
    success_url = reverse_lazy('personal_tab:overview')
    template_name = 'cookie_corner/authorization_terminate.html'

    def __init__(self, **kwargs):
        super(AuthorizationTerminateView, self).__init__(**kwargs)
        self.authorizations = Authorization.objects.to_terminate().order_by('id')\
            .select_related('authorization_type', 'person')

    def get_form_kwargs(self):
        kwargs = super(AuthorizationTerminateView, self).get_form_kwargs()
        kwargs['authorizations_queryset'] = self.authorizations
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(AuthorizationTerminateView, self).get_context_data(**kwargs)
        # Date on which old (pre-SEPA) authorizations are registered
        context['date_old_authorizations'] = DATE_PRE_SEPA_AUTHORIZATIONS
        context['authorizations'] = self.authorizations
        return context

    def form_valid(self, form):
        to_terminate = form.cleaned_data['authorizations']
        for authorization in to_terminate:
            # Terminate authorization
            authorization.end_date = datetime.date.today()
            authorization.save()

        transaction.on_commit(lambda: messages.success(self.request, _('End inactive mandates.')))
        return super(AuthorizationTerminateView, self).form_valid(form)

    @method_decorator(transaction.atomic)
    def dispatch(self, *args, **kwargs):
        return super(AuthorizationTerminateView, self).dispatch(*args, **kwargs)


class AuthorizationAnonymizeView(RequireBoardMixin, FormView):
    """
    View to anonymize old and unused mandates.
    """
    form_class = AuthorizationSelectForm
    success_url = reverse_lazy('personal_tab:overview')
    template_name = 'cookie_corner/authorization_anonymize.html'

    def __init__(self, **kwargs):
        super(AuthorizationAnonymizeView, self).__init__(**kwargs)
        self.authorizations = Authorization.objects.to_anonymize().order_by('id')\
            .select_related('authorization_type', 'person')

    def get_form_kwargs(self):
        kwargs = super(AuthorizationAnonymizeView, self).get_form_kwargs()
        kwargs['authorizations_queryset'] = self.authorizations
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(AuthorizationAnonymizeView, self).get_context_data(**kwargs)
        # Date on which old (pre-SEPA) authorizations are registered
        context['date_old_authorizations'] = DATE_PRE_SEPA_AUTHORIZATIONS
        context['authorizations'] = self.authorizations
        return context

    def form_valid(self, form):
        to_anonymize = list(form.cleaned_data['authorizations'].order_by('pk'))

        for authorization in to_anonymize:
            # Anonimize authorization
            authorization.anonymize()

        return render(self.request, "cookie_corner/authorization_anonymize_success.html", {
            'authorizations': to_anonymize,
        })

    @method_decorator(transaction.atomic)
    def dispatch(self, *args, **kwargs):
        return super(AuthorizationAnonymizeView, self).dispatch(*args, **kwargs)


@require_board
@transaction.atomic
def authorization_amendment(request, authorization_id):
    authorization = get_object_or_404(Authorization, id=authorization_id)

    if authorization.next_amendment():
        raise Http404(_('Already has an ongoing amendment'))

    if request.method == 'POST':
        form = AmendmentForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            iban = form.cleaned_data['iban']
            bic = form.cleaned_data['bic']
            reason = form.cleaned_data['reason']
            process_amendment(authorization, date, iban, bic, reason)
            return redirect(authorization)
    else:
        form = AmendmentForm()

    return render(request, 'cookie_corner_authorization_amendment.html', {
        'form': form,
        'authorization': authorization
    })


@require_board
def debt_collection_list(request):
    return render(request, 'cookie_corner_debt_collection_list.html', {
        'assignments': DebtCollectionAssignment.objects.all()
    })


def _instruction_totals(instructions):
    res = {}
    for k, v in instructions.items():
        res[k] = sum([i['sum'] for i in v])
    return res


@require_board
@transaction.atomic
def debt_collection_new(request):
    ams = timezone.get_default_timezone()

    # First possible execution date
    now = timezone.now()
    minimal_execution_date = (now + datetime.timedelta(days=8)).astimezone(ams).date()
    if minimal_execution_date.weekday() >= 5:
        # Saturday or sunday
        extradays = 7 - minimal_execution_date.weekday()
        minimal_execution_date = minimal_execution_date + datetime.timedelta(days=extradays)

    # Define variables so they are defined in the context

    contribution_instructions = {}
    contribution_totals = {}
    cookie_corner_instructions = {}
    cookie_corner_totals = {}

    # Redirect to a page based on GET (handy for links)
    if request.method == 'POST':
        form = DebtCollectionForm(minimal_execution_date, request.POST)
        if form.is_valid():
            end = form.cleaned_data['end'].astimezone(timezone.utc)
            contribution = form.cleaned_data['contribution']
            cookie_corner = form.cleaned_data['cookie_corner']

            # Construct data
            if contribution:
                year = current_association_year()
                contribution_instructions = generate_contribution_instructions(year)
                contribution_totals = _instruction_totals(contribution_instructions)
            else:
                contribution_instructions = {}
                contribution_totals = {}

            if cookie_corner:
                cookie_corner_instructions = generate_cookie_corner_instructions(end)
                cookie_corner_totals = _instruction_totals(cookie_corner_instructions)
            else:
                cookie_corner_instructions = {}
                cookie_corner_totals = {}

            if (contribution_instructions or cookie_corner_instructions) and 'save' in request.POST:
                if contribution_instructions:
                    contr_frst = filter_contribution_instructions(contribution_instructions['frst'], request.POST)
                    contr_rcur = filter_contribution_instructions(contribution_instructions['rcur'], request.POST)
                else:
                    contr_frst = []
                    contr_rcur = []

                if cookie_corner_instructions:
                    cookie_frst = filter_cookie_corner_instructions(cookie_corner_instructions['frst'],
                                                                    request.POST) + filter_cookie_corner_instructions(
                        cookie_corner_instructions['terminated_authorization_frst'], request.POST)
                    cookie_rcur = filter_cookie_corner_instructions(cookie_corner_instructions['rcur'],
                                                                    request.POST) + filter_cookie_corner_instructions(
                        cookie_corner_instructions['terminated_authorization_rcur'], request.POST)
                else:
                    cookie_frst = []
                    cookie_rcur = []

                if contr_frst or contr_rcur or cookie_frst or cookie_rcur:
                    assignment = DebtCollectionAssignment(description=form.cleaned_data['description'],
                                                          end=form.cleaned_data['end'])
                    assignment.save()

                    if contr_frst or cookie_frst:
                        frst_batch = DebtCollectionBatch(assignment=assignment,
                                                         execution_date=form.cleaned_data['execution_date'],
                                                         sequence_type=DebtCollectionBatch.SequenceTypes.FRST,
                                                         status=DebtCollectionBatch.StatusChoices.NEW)
                        frst_batch.save()

                        if contr_frst:
                            save_contribution_instructions(contr_frst, frst_batch)
                        if cookie_frst:
                            save_cookie_corner_instructions(cookie_frst, frst_batch)

                    if contr_rcur or cookie_rcur:
                        rcur_batch = DebtCollectionBatch(assignment=assignment,
                                                         execution_date=form.cleaned_data['execution_date'],
                                                         sequence_type=DebtCollectionBatch.SequenceTypes.RCUR,
                                                         status=DebtCollectionBatch.StatusChoices.NEW)
                        rcur_batch.save()

                        if contr_rcur:
                            save_contribution_instructions(contr_rcur, rcur_batch)
                        if cookie_rcur:
                            save_cookie_corner_instructions(cookie_rcur, rcur_batch)
                    return redirect(assignment)

    else:
        end_date = timezone.datetime(year=now.year, month=now.month, day=now.day)
        date_text = formats.date_format(end_date)
        form = DebtCollectionForm(minimal_execution_date,
                                  initial={'description': 'Cookie corner and contribution until {}'.format(date_text),
                                    'contribution': True, 'cookie_corner': True, 'end': end_date})

    return render(request, 'cookie_corner_debt_collection_new.html', {
        'form': form,
        'minimal_execution_date': minimal_execution_date,
        'contribution_instructions': contribution_instructions,
        'contribution_totals': contribution_totals,
        'cookie_corner_instructions': cookie_corner_instructions,
        'cookie_corner_totals': cookie_corner_totals
    })


@require_board
def debt_collection_view(request, id):
    assignment = get_object_or_404(DebtCollectionAssignment, id=id)

    if request.method == "POST":
        export_form = ExportForm(request.POST, rows=1)
        if export_form.is_valid():
            # Save the data export information and retrieve the export type to determine what to do.
            dei_id, export_type = export_form.save_data_export_information(request.user.person)

            if export_type == "cookie_corner_sepa_export":
                # Actually export the data by directly calling the debt collection export view function.
                return debt_collection_export(request, id)

            else:
                # Redirect back to debt collection view with an error message.
                messages.warning(request, _(
                    "Could not create data export, because an unknown data-exporttype is provided."
                ))
                return redirect('personal_tab:debt_collection_view', id)

        else:
            # Redirect back to debt collection view with an error message.
            messages.warning(request, _(
                "Could not create data export, because something went wrong while saving information about the export."
            ))
            return render(request, 'cookie_corner_debt_collection_view.html', locals())

    else:
        export_form = ExportForm(rows=1)
        export_form.fields['export_details'].initial = str(assignment)
        return render(request, 'cookie_corner_debt_collection_view.html', locals())


def debt_collection_export(request, id):
    """
    Export the debt collection to a SEPA file.

    WARNING: This view should NOT be used directly in a URL!
    It should instead be called in another view after the GDPR ExportForm has been filled in properly and a
    DataExportInformation object has been created for this specified data export!
    """
    assignment = get_object_or_404(DebtCollectionAssignment, id=id)

    response = render(request, 'exports/sepadd.xml', locals(), content_type='application/xml; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=%s.xml' % (assignment.file_identification())
    return response


@login_required
def debt_collection_instruction_view(request, id):
    instruction = get_object_or_404(DebtCollectionInstruction, id=id)
    if not request.is_board and request.person != instruction.authorization.person:
        raise PermissionDenied
    return render(request, 'cookie_corner_debt_collection_instruction_view.html', {
        'instruction': instruction
    })


@require_board
@transaction.atomic
def debt_collection_instruction_reversal(request, id):
    instruction = get_object_or_404(DebtCollectionInstruction, id=id)
    if hasattr(instruction, 'reversal'):
        raise Http404(_('Reversal already exists'))

    if request.method == 'POST':
        form = ReversalForm(request.POST)
        if form.is_valid():
            reversal = form.save(commit=False)
            reversal.instruction = instruction
            reversal.save()
            process_reversal(reversal, request.person)
            return redirect(instruction)
    else:
        form = ReversalForm()

    return render(request, 'cookie_corner_debt_collection_instruction_reversal.html', {
        'form': form,
        'instruction': instruction
    })


@require_board
def debt_collection_mailing(request, assignment_id):
    assignment = get_object_or_404(DebtCollectionAssignment, id=assignment_id)

    has_contribution = DebtCollectionInstruction.objects.filter(
        batch__assignment=assignment,
        authorization__authorization_type__contribution=True
    ).exists()
    has_cookie_corner = DebtCollectionInstruction.objects.filter(
        batch__assignment=assignment,
        authorization__authorization_type__contribution=False
    ).exists()

    return render(request, 'cookie_corner_debt_collection_mailing.html', {
        'assignment': assignment,
        'has_contribution': has_contribution,
        'has_cookie_corner': has_cookie_corner
    })


@require_board
def process_batch(request, id):
    batch = get_object_or_404(DebtCollectionBatch, id=id)
    if request.POST:
        form = DebtCollectionBatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            return redirect('personal_tab:debt_collection_view', id=batch.assignment.id)
    else:
        form = DebtCollectionBatchForm(instance=batch)

    return render(request, 'cookie_corner_process_batch.html', {
        'form': form,
        'batch': batch,
    })


def _get_person_context(instruction):
    """
    Give the Person object and context dict for a DebtCollectionInstruction.
    :param instruction: DebtCollectionInstruction.
    :type instruction: DebtCollectionInstruction
    :return: Dict containing a Person object and a context dict.
    """
    person = instruction.authorization.person
    context = {
        'instruction': {
            'batch': {
                'assignment': {
                    'end': instruction.batch.assignment.end
                },
                'execution_date': instruction.batch.execution_date
            },
            'amount': instruction.amount,
            'end_to_end_id': instruction.end_to_end_id,
            'id': instruction.id,
            'authorization': {
                'iban': instruction.authorization.iban,
                'authorization_reference': instruction.authorization.authorization_reference()
            }
        }
    }

    return person, context


def _get_person_context_contribution(instruction):
    """
    Give the Person object and context dict for a DebtCollectionInstruction with membership fee transaction.
    :param instruction: DebtCollectionInstruction with membership fee transaction.
    :type instruction: DebtCollectionInstruction
    :return: Dict containing a Person object and a context dict.
    """
    person, context = _get_person_context(instruction)

    membership = Membership.objects.get(contributiontransaction__debt_collection=instruction)
    context['membership'] = {
        'type': membership.type.name
    }

    return person, context


@require_board
def debt_collection_mailing_contribution(request, assignment_id):
    assignment = get_object_or_404(DebtCollectionAssignment, id=assignment_id)

    instructions = DebtCollectionInstruction.objects.filter(batch__assignment=assignment,
                                                            authorization__authorization_type__contribution=True)
    persons = Person.objects.filter(authorization__instructions__in=instructions).distinct()

    current_year = current_association_year()
    study_year = '{}/{}'.format(current_year, current_year + 1)
    name_treasurer = request.person.incomplete_name()

    form = MailingForm(data=request.POST or None, initial={
        'sender': '[Inter-Actief] {}'.format(name_treasurer),
        'email': 'penningmeester@inter-actief.net',
        'subject_nl': '[Inter-Actief] Automatische incasso contributie {}'.format(study_year),
        'template_nl': '''Beste {{{{recipient.first_name}}}},

Op {{{{instruction.batch.execution_date}}}} zal de incasso voor de contributie voor studievereniging Inter-Actief van collegejaar {} plaatsvinden.

Het betreft het volgende lidmaatschap:
 * Naam: {{{{recipient.incomplete_name}}}}
 * Woonplaats: {{{{recipient.city}}}}
 * Type lidmaatschap: {{{{membership.type}}}}
 * Kosten: {{{{instruction.amount}}}} euro

Het bedrag zal geïncasseerd worden van rekening {{{{instruction.authorization.iban}}}}. Probeer ervoor te zorgen dat er dan voldoende saldo op deze rekening staat.

De incasso wordt gekenmerkt door het volgende:
Incassant-ID: NL81ZZZ400749470000
Machtigingskenmerk: {{{{instruction.authorization.authorization_reference}}}}
Referentie: {{{{instruction.end_to_end_id}}}}

Met vriendelijke groet,

{}
Penningmeester'''.format(study_year, name_treasurer),
        'subject_en': '[Inter-Actief] Direct debit contribution {}'.format(study_year),
        'template_en': '''Dear {{{{recipient.first_name}}}},

On {{{{instruction.batch.execution_date}}}} the direct debit for the contribution of study association Inter-Actief for college year {} will be debited.

It concerns the following membership:
 * Name: {{{{recipient.incomplete_name}}}}
 * Place of residence: {{{{recipient.city}}}}
 * Membership type: {{{{membership.type}}}}
 * Costs: {{{{instruction.amount}}}} euro

The amount will be debited from bank account {{{{instruction.authorization.iban}}}}. Try to ensure that your account balance is sufficient.

The direct debit is referenced by the following:
Creditor identifier: NL81ZZZ400749470000
Mandate reference: {{{{instruction.authorization.authorization_reference}}}}
Reference: {{{{instruction.end_to_end_id}}}}

Kind regards,

{}
Treasurer'''.format(study_year, name_treasurer),
    })

    if not persons:
        # No persons found, give 404
        raise Http404(_("Found nobody."))

    # Variables are used in template, don't remove!
    longest_first_name = max([p.first_name for p in persons if p.first_name is not None], key=len)
    longest_last_name = max([p.last_name for p in persons if p.last_name is not None], key=len)
    longest_address = max([p.address for p in persons if p.address is not None], key=len)
    longest_postal_code = max([p.postal_code for p in persons if p.postal_code is not None], key=len)
    longest_city = max([p.city for p in persons if p.city is not None], key=len)
    longest_country = max([p.country for p in persons if p.country is not None], key=len)
    longest_student_number = '0123456'

    previews = None
    if request.method == "POST" and form.is_valid():
        if request.POST.get('preview', None):
            person, context = _get_person_context_contribution(instructions[0])
            previews = form.build_multilang_preview(person, context=context)
        else:
            recipients = [_get_person_context_contribution(instruction) for instruction in instructions]

            task = form.build_task(recipients)
            task.send()

            # Done
            return render(request, 'message.html', {
                'message': 'De mails worden nu een voor een verstuurd. '
                           'Dit gebeurt in een achtergrondproces en kan even duren.'
            })

    return render(request, 'includes/query/query_mailing.html', {
        'previews': previews,
        'persons': persons,
        'longest_first_name': longest_first_name,
        'longest_last_name': longest_last_name,
        'longest_address': longest_address,
        'longest_postal_code': longest_postal_code,
        'longest_city': longest_city,
        'longest_country': longest_country,
        'longest_student_number': longest_student_number,
        'form': form,
    })


@require_board
def debt_collection_mailing_cookie_corner(request, assignment_id):
    assignment = get_object_or_404(DebtCollectionAssignment, id=assignment_id)

    instructions = DebtCollectionInstruction.objects.filter(batch__assignment=assignment,
                                                            authorization__authorization_type__contribution=False)
    name_treasurer = request.person.incomplete_name()

    persons = Person.objects.filter(authorization__instructions__in=instructions).distinct()
    form = MailingForm(data=request.POST or None, initial={
        'sender': '[Inter-Actief] {}'.format(name_treasurer),
        'email': 'penningmeester@inter-actief.net',
        'subject_nl': '[Inter-Actief] Automatische incasso streeplijst t/m {{instruction.batch.assignment.end}}',
        'template_nl': '''Beste {{{{recipient.first_name}}}},

Je hebt een machtiging getekend voor het incasseren van de gekochte consumpties en/of activiteiten. Je hoort hierbij een week voor de afschrijving bericht te krijgen van de afschrijving.

Op {{{{instruction.batch.execution_date}}}} zal de incasso voor transacties tot {{{{instruction.batch.assignment.end}}}} plaatsvinden. Er zal {{{{instruction.amount}}}} euro geïncasseerd worden. Details van de transacties kan je vinden op https://www.inter-actief.utwente.nl/personal_tab/debt_collection_instruction/{{{{instruction.id}}}}/.

Het bedrag zal geïncasseerd worden van rekening {{{{instruction.authorization.iban}}}}. Probeer ervoor te zorgen dat er dan voldoende saldo op deze rekening staat.

De incasso wordt gekenmerkt door het volgende:
Incassant-ID: NL81ZZZ400749470000
Machtigingskenmerk: {{{{instruction.authorization.authorization_reference}}}}
Referentie: {{{{instruction.end_to_end_id}}}}

Met vriendelijke groet,

{}
Penningmeester'''.format(name_treasurer),
        'subject_en': '[Inter-Actief] Direct debit cookie corner up until {{instruction.batch.assignment.end}}',
        'template_en': '''Dear {{{{recipient.first_name}}}},

You have signed a mandate for the direct debit of the purchased consumptions and/or activities. You are supposed to be notified of the payment a week in advance.

On {{{{instruction.batch.execution_date}}}} the direct debit for the transactions until {{{{instruction.batch.assignment.end}}}} will take place. €{{{{instruction.amount}}}} will be debited. Details of the transactions can be found on https://www.inter-actief.utwente.nl/personal_tab/debt_collection_instruction/{{{{instruction.id}}}}/.

The amount will be debited from bank account {{{{instruction.authorization.iban}}}}. Try to ensure that your account balance is sufficient.

The direct debit is referenced by the following:
Creditor identifier: NL81ZZZ400749470000
Mandate reference: {{{{instruction.authorization.authorization_reference}}}}
Reference: {{{{instruction.end_to_end_id}}}}

Kind regards,

{}
Treasurer'''.format(name_treasurer),
    })

    if not persons:
        # No persons found, give 404
        raise Http404(_("Found nobody."))

    # Variables are used in template, don't remove!
    longest_first_name = max([p.first_name for p in persons if p.first_name is not None], key=len)
    longest_last_name = max([p.last_name for p in persons if p.last_name is not None], key=len)
    longest_address = max([p.address for p in persons if p.address is not None], key=len)
    longest_postal_code = max([p.postal_code for p in persons if p.postal_code is not None], key=len)
    longest_city = max([p.city for p in persons if p.city is not None], key=len)
    longest_country = max([p.country for p in persons if p.country is not None], key=len)
    longest_student_number = '0123456'

    previews = None
    if request.method == "POST" and form.is_valid():
        if request.POST.get('preview', None):
            person, context = _get_person_context(instructions[0])
            previews = form.build_multilang_preview(person, context=context)
        else:
            recipients = [_get_person_context(instruction) for instruction in instructions]

            task = form.build_task(recipients)
            task.send()

            # Done
            return render(request, 'message.html', {
                'message': _('The mails are now being sent one by one. '
                             'This happens in a background process and might take a while.')
            })

    return render(request, 'includes/query/query_mailing.html', {
        'previews': previews,
        'persons': persons,
        'longest_first_name': longest_first_name,
        'longest_last_name': longest_last_name,
        'longest_address': longest_address,
        'longest_postal_code': longest_postal_code,
        'longest_city': longest_city,
        'longest_country': longest_country,
        'longest_student_number': longest_student_number,
        'form': form,
    })


@require_board
def authorization_view(request, authorization_id):
    return render(request, 'cookie_corner_authorization_view.html', {
        'authorization': get_object_or_404(Authorization, id=authorization_id)
    })


"""
Cookie Corner Wrapped
"""


@require_lid
def cookie_corner_wrapped_main(request, year=None):
    # Only allow specifying a year if the year is in the past
    current_year = datetime.date.today().year
    if year is not None and year < current_year:
        COOKIE_CORNER_WRAPPED_YEAR = year
    elif year is not None:
        # Redirect to the non-year view
        return redirect("personal_tab:cookie_corner_wrapped")
    else:
        COOKIE_CORNER_WRAPPED_YEAR = django.conf.settings.COOKIE_CORNER_WRAPPED_YEAR

    person = request.person
    language = get_language()

    transaction_years = sorted(list(set(
        CookieCornerTransaction.objects.filter(person=person).values_list('date__year', flat=True).distinct()
    )))
    # Remove current year if present
    if current_year in transaction_years:
        transaction_years.remove(current_year)

    transactions = CookieCornerTransaction.objects.filter(
        person=person,
        date__year=COOKIE_CORNER_WRAPPED_YEAR
    ).all()

    if len(transactions) == 0:
        # No transactions found, display the no transactions page
        return render(request, 'wrapped_no_transactions.html', {
            'year': COOKIE_CORNER_WRAPPED_YEAR,
            'transaction_years': transaction_years,
        })

    transaction_count = transactions \
        .annotate(day=TruncDay('date')) \
        .values('day') \
        .annotate(c=Count('id')) \
        .values('day', 'c')

    first_transaction_of_the_year = transactions.earliest('date')
    last_transaction_of_the_year = transactions[0]

    most_transactions_day = transaction_count.order_by('c').last()
    most_transactions_date = most_transactions_day['day']
    most_transactions_list = transactions.filter(
        date__month=most_transactions_date.month,
        date__day=most_transactions_date.day
    ).all()

    total_price = 0
    total_kcal = 0

    for transaction in most_transactions_list:
        total_price += transaction.article.price
        total_kcal += transaction.article.kcal if transaction.article.kcal is not None else 0

    """
        Products
    """
    products_grouped_by_count = {}

    total = {
        'kcal': 0,
        'price': 0
    }

    for transaction in transactions:
        article = transaction.article
        amount = transaction.amount

        kcal = transaction.kcal()

        total['kcal'] += kcal if kcal is not None else 0
        total['price'] += transaction.price

        if article in products_grouped_by_count:
            products_grouped_by_count[article] += amount
        else:
            products_grouped_by_count[article] = amount

    products_grouped_by_count = sorted(products_grouped_by_count.items(), key=lambda x:x[1])

    products_grouped_by_count.reverse()

    top_5_products = products_grouped_by_count[:5]

    total['equivalent'] = kcal_equivalent(total['kcal'], language)

    """
        Alexia
    """

    alexia_transactions = AlexiaTransaction.objects.filter(
        person=person,
        date__year=COOKIE_CORNER_WRAPPED_YEAR
    )

    drink_spend_most = alexia_transactions \
        .values('description', 'date__day', 'date__month') \
        .annotate(total_price=Sum('price')) \
        .order_by('-total_price', '-date__day', '-date__month')

    drinks_total = sum(d['total_price'] for d in drink_spend_most)

    return render(request, 'wrapped.html', {
        'year': COOKIE_CORNER_WRAPPED_YEAR,
        'transaction_years': transaction_years,
        'first_transaction_of_the_year': first_transaction_of_the_year,
        'last_transaction_of_the_year': last_transaction_of_the_year,
        'most_transactions': {
            'day': most_transactions_day,
            'list': most_transactions_list,
            'total_price': total_price,
            'total_kcal': total_kcal,
        },
        'top_5_products': top_5_products,
        'total': total,
        'drink_spend_most': drink_spend_most,
        'drinks_total': drinks_total
    })

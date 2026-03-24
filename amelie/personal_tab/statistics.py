from django.db import connection
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay
from django.utils.translation import gettext_lazy as _l

from amelie.calendar.models import Event
from amelie.members.models import MembershipType
from amelie.personal_tab.models import Discount, DiscountPeriod, CustomTransaction, DiscountCredit, \
    ContributionTransaction, AlexiaTransaction, ActivityTransaction, \
    CookieCornerTransaction, LedgerAccount, Category, Article


def statistics_totals(start, end, tables):
    names = {x[1]: x[2] for x in get_functions()}
    rows = [(names[x], tables[x]['sum'] if x in tables else TOTAL_FUNCTIONS[x](start, end)) for x in TOTAL_FUNCTIONS]
    return {'rows': rows, 'sum': sum(x[1] for x in rows)}


def statistics_cookie_corner_ledger_breakdown(ledger):
    """Create a statistics function for a breakdown of a certain ledger account"""
    all_articles = {article.pk: article for article in ledger.articles.all()}

    def statistics_cookie_corner_breakdown_for_ledger(start, end):
        cookie_corner_transactions = CookieCornerTransaction.objects.filter(date__gte=start, date__lt=end) \
            .filter(article__in=all_articles.values())

        rows = []
        articles_aggregator = cookie_corner_transactions\
            .values('article').order_by('article').annotate(Sum('amount'), Sum('price'), Sum('discount__amount'))

        for article_aggregation in articles_aggregator:
            if article_aggregation['amount__sum']:
                article_sum = article_aggregation['price__sum']
                article_discount_sum = article_aggregation['discount__amount__sum']

                rows.append({
                    'article': all_articles[article_aggregation['article']],
                    'count': article_aggregation['amount__sum'],
                    'discount': article_discount_sum,
                    'sum': article_sum,
                    'total': article_sum + (article_discount_sum or 0)
                })

        # Total row
        ledger_aggregation = cookie_corner_transactions.aggregate(
                Sum('amount'), Sum('price'), Sum('discount__amount'))

        ledger_sum = ledger_aggregation['price__sum'] or 0
        ledger_discount_sum = ledger_aggregation['discount__amount__sum']

        total = {
            'count': ledger_aggregation['amount__sum'] or 0,
            'discount': ledger_discount_sum,
            'sum': ledger_sum,
            'total': ledger_sum + (ledger_discount_sum or 0)
        }

        return {'rows': rows, 'total': total}

    return statistics_cookie_corner_breakdown_for_ledger


def statistics_cookie_corner_breakdown(start, end):
    cookie_corner_transactions = CookieCornerTransaction.objects.filter(date__gte=start, date__lt=end)

    categories = cookie_corner_transactions.order_by().distinct().values('article__category')

    rows = []
    for c in categories:
        category = Category.objects.get(id=c['article__category'])
        category_transactions = cookie_corner_transactions.filter(article__category_id=category)
        category_aggregation = category_transactions.aggregate(Sum('amount'), Sum('price'), Sum('discount__amount'))
        category_count = category_aggregation['amount__sum'] or 0
        category_sum = category_aggregation['price__sum'] or 0
        category_discount_sum = category_aggregation['discount__amount__sum'] or 0
        category_total = category_sum + category_discount_sum

        articles = category_transactions.order_by().distinct().values('article')

        cat_rows = []

        for a in articles:
            article = Article.objects.get(id=a['article'])
            article_aggregation = category_transactions.filter(article=article).aggregate(Sum('amount'), Sum('price'),
                                                                                          Sum('discount__amount'))

            article_count = article_aggregation['amount__sum']
            article_sum = article_aggregation['price__sum']
            article_discount_sum = article_aggregation['discount__amount__sum']
            article_total = article_sum + (article_discount_sum or 0)

            cat_rows.append({
                'article': article,
                'count': article_count,
                'discount': article_discount_sum,
                'sum': article_sum,
                'total': article_total
            })

        rows.append({
            'category': category,
            'articles': cat_rows,
            'count': category_count,
            'discount': category_discount_sum,
            'sum': category_sum,
            'total': category_total
        })
    return {'rows': rows}


def statistics_cookie_corner_totals(start, end):
    cookie_corner_transactions = CookieCornerTransaction.objects.filter(date__gte=start, date__lt=end)
    rows = []
    for ledger_account in cookie_corner_transactions.order_by().distinct().values('article__ledger_account'):
        rows.append(_statistics_cookie_corner_totals_category(cookie_corner_transactions,
                                                              ledger_account['article__ledger_account']))
    totals = [sum(x[i] for x in rows if x) for i in range(1, 5)]
    return {'rows': rows, 'sum': totals[-1], 'totals': totals}


def _statistics_cookie_corner_totals_category(cookie_corner_transactions, ledger_account):
    transactions = cookie_corner_transactions.filter(article__ledger_account_id=ledger_account)
    totals = transactions.aggregate(Sum('amount'), Sum('price'), Sum('discount__amount'))
    amount = totals['amount__sum'] or 0
    paid = totals['price__sum'] or 0
    discount = totals['discount__amount__sum'] or 0
    total = paid + discount
    return [LedgerAccount.objects.get(id=ledger_account), amount, discount, paid, total]


def statistics_cookie_corner_total(start, end):
    totals = CookieCornerTransaction.objects.filter(date__gte=start, date__lt=end).aggregate(Sum('price'),
                                                                                             Sum('discount__amount'))
    return (totals['price__sum'] or 0) + (totals['discount__amount__sum'] or 0)


def statistics_activities(start, end):
    """Returns activity transaction statistics over a certain period"""
    activity_transactions = ActivityTransaction.objects.filter(date__gte=start, date__lt=end)

    number_of_transactions = activity_transactions.count()
    number_of_enrollments = activity_transactions.filter(participation__isnull=False).count()
    total = activity_transactions.aggregate(Sum('price'))['price__sum'] or 0

    # Do not use order, so that distinct works well. See Django manual.
    events = activity_transactions.order_by().distinct().values('event')

    rows = []
    for e in events:
        try:
            event = Event.objects.get(id=e['event'])
        except Event.DoesNotExist:
            event = None

        event_transaction_count = activity_transactions.filter(event=event).count()
        event_active_transaction_count = activity_transactions.filter(event=event, participation__isnull=False).count()
        event_transaction_sum = activity_transactions.filter(event=event).aggregate(Sum('price'))['price__sum']
        rows.append({
            'event': event,
            'count': event_transaction_count,
            'active_count': event_active_transaction_count,
            'sum': event_transaction_sum
        })
    return {'rows': rows, 'sum': total, 'count': number_of_transactions, 'active_count': number_of_enrollments}


def statistics_activities_total(start, end):
    return ActivityTransaction.objects.filter(date__gte=start, date__lt=end).aggregate(Sum('price'))['price__sum'] or 0


def statistics_contribution_transactions(start, end):
    contribution_transactions = ContributionTransaction.objects.filter(date__gte=start, date__lt=end)
    contribution_sum = contribution_transactions.aggregate(Sum('price'))['price__sum'] or 0

    # Do not use order, so that values works well. See Django manual.
    sum_per_membership_type = contribution_transactions.order_by().values('membership__type').annotate(Sum('price'))
    sum_per_membership_type_dict = {x['membership__type']: x['price__sum'] for x in sum_per_membership_type}

    # Count positive and negative transactions
    positive_transactions_per_membership_type = contribution_transactions.filter(price__gt=0).order_by().values(
        'membership__type').annotate(Count('price'))
    positive_transactions_per_membership_type_dict = {x['membership__type']: x['price__count']
                                                      for x in positive_transactions_per_membership_type}
    negative_transactions_per_membership_type = contribution_transactions.filter(price__lt=0).order_by().values(
        'membership__type').annotate(Count('price'))
    negative_transactions_per_membership_type_dict = {x['membership__type']: x['price__count']
                                                      for x in negative_transactions_per_membership_type}

    types = MembershipType.objects.filter(pk__in=sum_per_membership_type_dict.keys())

    type_totals = []

    for membership_type in types:
        if sum_per_membership_type_dict[membership_type.pk]:
            positive_transactions = positive_transactions_per_membership_type_dict.get(membership_type.pk, 0)
            negative_transactions = negative_transactions_per_membership_type_dict.get(membership_type.pk, 0)
            type_totals.append({
                'membership_type': membership_type,
                'amount': positive_transactions - negative_transactions,
                'total': sum_per_membership_type_dict[membership_type.pk]
            })
    return {'rows': type_totals, 'sum': contribution_sum}


def statistics_contribution_transactions_total(start, end):
    return ContributionTransaction.objects.filter(date__gte=start, date__lt=end).aggregate(
        Sum('price'))['price__sum'] or 0


def statistics_discount_periods(start, end):
    discount_transactions = Discount.objects.filter(date__gte=start, date__lt=end)
    discount_sum = discount_transactions.aggregate(Sum('amount'))['amount__sum'] or 0
    discount_aggregated = discount_transactions.order_by().values('discount_period').annotate(
        Count('amount'), Sum('amount')).order_by('discount_period')

    rows = []

    for discount in discount_aggregated:
        discount_period = DiscountPeriod.objects.get(id=discount['discount_period'])

        discount_count = discount['amount__count']
        discount_sum = discount['amount__sum']

        rows.append({
            'discount_period': discount_period,
            'count': discount_count,
            'sum': discount_sum
        })

    return {'rows': rows, 'sum': discount_sum}


def statistics_other_transactions(start, end):
    rows = CustomTransaction.objects.filter(date__gte=start, date__lt=end).select_related('person')
    count = rows.count()
    custom_sum = rows.aggregate(Sum('price'))['price__sum'] or 0
    return {'rows': rows, 'count': count, 'sum': custom_sum}


def statistics_other_transactions_total(start, end):
    return CustomTransaction.objects.filter(date__gte=start, date__lt=end).aggregate(Sum('price'))['price__sum'] or 0


def statistics_discount_credits(start, end):
    transactions = DiscountCredit.objects.filter(date__gte=start, date__lt=end, discount__isnull=True)
    credit_count = transactions.count()
    credit_sum = transactions.aggregate(Sum('price'))['price__sum'] or 0
    credit_aggregated = transactions.order_by().values('discount_period').annotate(
        Count('price'), Sum('price')).order_by('discount_period')

    rows = []
    for credit in credit_aggregated:
        discount_period = DiscountPeriod.objects.get(id=credit['discount_period'])
        row = {'discount_period': discount_period, 'count': credit['price__count'], 'sum': credit['price__sum'], }
        rows.append(row)
    return {'count': credit_count, 'rows': rows, 'sum': credit_sum}


def statistics_alexia_transactions(start, end):
    alexia_transactions = AlexiaTransaction.objects.filter(date__gte=start, date__lt=end)
    alexia_sum = alexia_transactions.aggregate(Sum('price'))['price__sum'] or 0

    # https://stackoverflow.com/questions/8746014/django-group-sales-by-month
    alexia_rows = alexia_transactions.annotate(day=TruncDay('date')).values('day', 'description').annotate(
        Sum('price')).order_by('day', 'description')
    return {'header': [_l('Name')], 'rows': alexia_rows, 'sum': alexia_sum}


def statistics_alexia_transactions_total(start, end):
    return AlexiaTransaction.objects.filter(date__gte=start, date__lt=end).aggregate(Sum('price'))['price__sum'] or 0


def statistics_functions_ledgers():
    return [(statistics_cookie_corner_ledger_breakdown(ledger),
             'l{}'.format(ledger.pk),
             _l('{} ledger statistics').format(ledger.name.capitalize()),
             ledger.default_statistics)
            for ledger in LedgerAccount.objects.all()]


def get_functions():
    return [
        (statistics_cookie_corner_breakdown, 'u', _l('Personal tab statistics'), False),
        (statistics_cookie_corner_totals, 's', _l('Personal tab balance'), True),
        (statistics_activities, 'a', _l('Activities'), True),
        (statistics_alexia_transactions, 'x', _l('Alexia transactions'), False),
        (statistics_contribution_transactions, 'c', _l('Contribution transactions'), True),
        (statistics_discount_periods, 'k', _l('Discount offers'), True),
        (statistics_discount_credits, 'g', _l('Discount balances'), True),
        (statistics_other_transactions, 'o', _l('Custom transactions'), True),
        (statistics_totals, 't', _l('Totals'), True),
    ] + statistics_functions_ledgers()


TOTAL_FUNCTIONS = {'s': statistics_cookie_corner_total,
                   'a': statistics_activities_total,
                   'x': statistics_alexia_transactions_total,
                   'c': statistics_contribution_transactions_total,
                   'o': statistics_other_transactions_total}

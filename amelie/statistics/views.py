from datetime import datetime, date, time, timedelta

from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.shortcuts import render
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.files.models import Attachment
from amelie.members.models import Person, Committee, CommitteeCategory
from amelie.statistics.models import Hits
from amelie.personal_tab.models import CookieCornerTransaction, RFIDCard, Article, Transaction
from amelie.tools.decorators import require_lid, require_board
from amelie.tools.logic import current_academic_year_strict, association_year


@require_lid
def statistics(request):
    def calculate():
        # General statistics
        member_count = Person.objects.members().count()
        active_member_count = Person.objects.active_members().count()
        committee_count = Committee.objects.active().count()
        committee_category_count = CommitteeCategory.objects.all().count()

        begin_study_year = datetime(year=current_academic_year_strict(), month=9, day=1)\
            .replace(tzinfo=timezone.get_default_timezone())

        current_activity_count = Activity.objects.filter(begin__gt=begin_study_year, begin__lt=timezone.now())\
                                                      .count()
        activity_count = Activity.objects.filter(begin__lt=timezone.now()).count()

        # Photos
        albums_count = Activity.objects.distinct().filter(begin__lt=timezone.now(), photos__gt=0).count()
        photos_count = Attachment.objects.filter(thumb_medium__isnull=False).count()
        photographer_count = Attachment.objects.filter(thumb_medium__isnull=False).values('owner').distinct().count()

        # Personal Tab
        transactions_count = Transaction.objects.all().count()
        snacks_count = CookieCornerTransaction.objects.all().count()
        rfids_count = RFIDCard.objects.all().count()

        days = (CookieCornerTransaction.objects.all().order_by('-date')[0].date
                 - CookieCornerTransaction.objects.all().order_by('date')[0].date).days

        snacks_average_count = int(snacks_count / days)
        begin_today = datetime.combine(date.today(), time(0, 0))\
            .replace(tzinfo=timezone.get_default_timezone())
        snacks_today_count = CookieCornerTransaction.objects.filter(date__gt=begin_today).count()

        transactions = CookieCornerTransaction.objects.values('article').annotate(count=Count('article'))\
                                                                        .order_by('-count')[:5]

        popular_snacks = ["%s (%dx)" % (Article.objects.get(pk=x['article']), x['count']) for x in transactions]

        board_transactions = CookieCornerTransaction.objects.filter(person__in=Person.objects.board()).values('person')\
                                                     .annotate(count=Count('person')).order_by('-count')[:1]
        healthiest_board_member = str(Person.objects.get(pk=board_transactions[0]['person'])) if len(board_transactions) > 0 else None

        # Done!
        return locals()

    # From cache, or calculate anew.
    stats = cache.get('statistics')

    if not stats:
        stats = calculate()
        cache.set('statistics', stats, 3600)

    if Transaction.objects.exists():
        stats['year_range'] = range(Transaction.objects.all().order_by('date').first().added_on.year, Transaction.objects.all().order_by('date').last().added_on.year + 1)
    else:
        stats['year_range'] = range(timezone.now().date().year, timezone.now().date().year + 1)

    # Done!
    return render(request, "statistics.html", stats)


@require_board
def statistics_year(request, year: int):
    def calculate(year_dt):
        # General statistics
        member_count = Person.objects.members_at(year_dt.date()).count()
        active_member_count = Person.objects.active_members_at(year_dt.date()).count()
        committee_count = Committee.objects.active_at(year_dt.date()).count()

        begin_study_year = datetime(year=current_academic_year_strict(dt=year_dt), month=9, day=1)\
            .replace(tzinfo=timezone.get_default_timezone())
        end_study_year = datetime(year=current_academic_year_strict(dt=year_dt)+1, month=8, day=31)\
            .replace(tzinfo=timezone.get_default_timezone())

        current_activity_count = Activity.objects.filter(begin__gt=begin_study_year, begin__lt=end_study_year)\
                                                      .count()

        # Photos
        albums_count = Activity.objects.distinct().filter(begin__gt=begin_study_year, begin__lt=end_study_year,
                                                          photos__gt=0).count()
        photos_count = Attachment.objects.filter(created__gt=begin_study_year, created__lt=end_study_year,
                                                 thumb_medium__isnull=False).count()
        photographer_count = Attachment.objects.filter(created__gt=begin_study_year, created__lt=end_study_year,
                                                       thumb_medium__isnull=False).values('owner').distinct().count()

        # Personal Tab
        transactions_count = Transaction.objects.filter(added_on__gt=begin_study_year, added_on__lt=end_study_year).count()
        snacks_count = CookieCornerTransaction.objects.filter(added_on__gt=begin_study_year, added_on__lt=end_study_year).count()
        rfids_count = RFIDCard.objects.filter(created__gt=begin_study_year, created__lt=end_study_year).count()

        cc_transactions = CookieCornerTransaction.objects.filter(added_on__gt=begin_study_year, added_on__lt=end_study_year).order_by('date')
        last_transaction = cc_transactions.last()
        first_transaction = cc_transactions.first()
        if first_transaction and last_transaction:
            days = (last_transaction.date - first_transaction.date).days
            if days < 0:  # Protect against division by 0 and negative division
                days = 1
        else:
            days = 1  # Protect against division by 0

        snacks_average_count = int(snacks_count / days)

        transactions = CookieCornerTransaction.objects.filter(added_on__gt=begin_study_year, added_on__lt=end_study_year)\
                .values('article').annotate(count=Count('article')).order_by('-count')[:5]

        popular_snacks = ["%s (%dx)" % (Article.objects.get(pk=x['article']), x['count']) for x in transactions]


        # Get the board members in this specific year, looking at the months November-May to avoid GMM/switchover strangeness
        begin_association_year = datetime(year=association_year(dt=year_dt), month=11, day=1)\
            .replace(tzinfo=timezone.get_default_timezone())
        end_association_year = datetime(year=association_year(dt=year_dt)+1, month=5, day=30)\
            .replace(tzinfo=timezone.get_default_timezone())
        board_members_in_year = Person.objects.active_members_at(year_dt).filter(
            Q(function__committee__abbreviation="Bestuur"),
            Q(function__begin__lt=begin_association_year),
            Q(function__end__isnull=True) | Q(function__end__gt=end_association_year)
        ).distinct()

        board_transactions = CookieCornerTransaction.objects.filter(added_on__gt=begin_study_year, added_on__lt=end_study_year)\
            .filter(person__in=board_members_in_year).values('person')\
            .annotate(count=Count('person')).order_by('-count')[:1]
        healthiest_board_member = str(Person.objects.get(pk=board_transactions[0]['person'])) if len(board_transactions) > 0 else None

        # Done!
        return locals()

    # From cache, or calculate anew.
    stats = cache.get(f'statistics_{year}')

    if not stats:
        # Get statistics at the last month of the academic year, on 1 June
        year_datetime = datetime(year=year, month=6, day=1)
        stats = calculate(year_dt=year_datetime)
        cache.set(f'statistics_{year}', stats, 3600)

    # Add year to context for template
    stats['year'] = year
    stats['year1'] = year + 1
    if Transaction.objects.exists():
        stats['year_range'] = range(Transaction.objects.all().order_by('date').first().added_on.year, Transaction.objects.all().order_by('date').last().added_on.year + 1)
    else:
        stats['year_range'] = range(timezone.now().date().year, timezone.now().date().year + 1)

    # Done!
    return render(request, "statistics_year.html", stats)


def hits(request):
    pages = []

    for values in Hits.objects.distinct().values('page'):
        page = values['page']

        pages.append({
            "name": page,
            "today": Hits.objects.filter(page=page, date_start=date.today())
                         .aggregate(Sum('hit_count'))['hit_count__sum'],
            "week": Hits.objects.filter(page=page, date_start__gte=date.today() - timedelta(days=7))
                         .aggregate(Sum('hit_count'))['hit_count__sum'],
            "month": Hits.objects.filter(page=page, date_start__gte=date.today() - timedelta(days=28))
                         .aggregate(Sum('hit_count'))['hit_count__sum'],
        })

    return render(request, 'hits.html', locals())

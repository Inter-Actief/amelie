from datetime import datetime, date, time, timedelta

from django.core.cache import cache
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.files.models import Attachment
from amelie.members.models import Person, Committee, CommitteeCategory
from amelie.statistics.models import Hits
from amelie.personal_tab.models import CookieCornerTransaction, RFIDCard, Article, Transaction
from amelie.tools.decorators import require_lid
from amelie.tools.logic import current_academic_year_strict


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

    context = {}
    context.update(stats)
    context["request"] = request

    # Done!
    return render(request, "statistics.html", stats)


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

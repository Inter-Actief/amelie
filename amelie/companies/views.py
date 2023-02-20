import datetime
import logging
import random

from django.urls import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from amelie.companies.forms import CompanyForm, BannerForm, TelevisionBannerForm, CompanyEventForm, StatisticsForm
from amelie.companies.models import BaseBanner, Company, CompanyEvent, TelevisionBanner, WebsiteBanner
from amelie.members.models import Committee
from amelie.statistics.decorators import track_hits
from amelie.tools.decorators import require_board
from amelie.tools.forms import PeriodForm
from amelie.tools.calendar import ical_calendar
from amelie.tools.mixins import RequireBoardMixin, RequireCommitteeMixin

logger = logging.getLogger(__name__)


@track_hits("Company Corner")
def company_overview(request):
    """ List of all companies """
    is_board = hasattr(request, 'person') and request.is_board
    should_sort = request.GET.get('sort') == 'name'

    if should_sort is True:
        companies = Company.objects.active()
    else:
        sorted_companies = Company.objects.active()

        # Randomly sort companies with the current date as seed for random number generator, such that the order on a
        # single day remains consistent.
        rand = random.Random(datetime.date.today().strftime('%d %m %Y'))
        companies = rand.sample(list(sorted_companies), sorted_companies.count())

    return render(request, 'companies/company_overview.html', {
        'is_board': is_board,
        'companies': companies,
        'active': True,
        'sorted': should_sort
    })


def company_details(request, slug):
    """ Shows details of a company """
    obj = get_object_or_404(Company, slug=slug)
    is_board = hasattr(request, 'person') and request.is_board
    return render(request, 'companies/company_details.html', {'obj': obj, 'is_board': is_board})


@require_board
def banner_list(request):
    """ List of all banners """
    website_banners = WebsiteBanner.objects.all()
    television_banners = TelevisionBanner.objects.all()
    today = datetime.date.today()
    return render(request, 'companies/company_banners.html', {'website_banners': website_banners, 'television_banners': television_banners, 'today': today})


@require_board
def banner_edit(request, id):
    """ Edit either a website banner or television banner. """
    obj = get_object_or_404(BaseBanner, id=id)
    form = None

    if request.method == "POST":
        if hasattr(obj, 'websitebanner'):
            form = BannerForm(request.POST, request.FILES, instance=obj.websitebanner)
        else:
            form = TelevisionBannerForm(request.POST, request.FILES, instance=obj.televisionbanner)

        if form.is_valid():
            form.save()

            return HttpResponseRedirect(reverse('companies:banner_list'))
    else:
        if hasattr(obj, 'websitebanner'):
            form = BannerForm(instance=obj.websitebanner)
        else:
            form = TelevisionBannerForm(instance=obj.televisionbanner)

    return render(request, 'companies/company_banners_form.html', locals())


@require_board
def websitebanner_create(request):
    """ Create a website banner. """
    if request.method == "POST":
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('companies:banner_list'))

    else:
        form = BannerForm()

    return render(request, 'companies/company_banners_form.html', locals())


@require_board
def televisionbanner_create(request):
    """ Create a television banner. """
    if request.method == "POST":
        form = TelevisionBannerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('companies:banner_list'))

    else:
        form = TelevisionBannerForm()

    return render(request, 'companies/company_banners_form.html', locals())


@require_board
def company_overview_old(request):
    """
    Overview with all inactive companies
    """
    is_board = hasattr(request, 'person') and request.is_board
    companies = Company.objects.inactive()
    return render(request, 'companies/company_overview.html', {
        'is_board': is_board,
        'companies': companies,
        'active': False
    })

@require_board
def company_edit(request, slug):
    """ Edit a company. """
    obj = get_object_or_404(Company, slug=slug)
    form = CompanyForm(instance=obj) if request.method != "POST" else CompanyForm(request.POST, request.FILES, instance=obj)
    is_new = False

    if request.method == "POST" and form.is_valid():
        company = form.save()
        return HttpResponseRedirect(company.get_absolute_url())

    return render(request, 'companies/company_form.html', locals())


@require_board
def company_create(request):
    """ Create a company. """
    form = CompanyForm() if request.method != "POST" else CompanyForm(request.POST, request.FILES)
    is_new = True

    if request.method == "POST" and form.is_valid():
        company = form.save()
        return HttpResponseRedirect(company.get_absolute_url())

    return render(request, 'companies/company_form.html', locals())


##
# Company calendar
##
@require_board
def event_create(request):
    """ Create a CompanyEvent. """
    is_new = True
    if request.method == 'POST':
        form = CompanyEventForm(data=request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = Committee.objects.get(name="Bestuur")
            event.public = True
            event.save()
            return HttpResponseRedirect(event.get_absolute_url())
    else:
        form = CompanyEventForm()

    return render(request, "companies/company_event_form.html", locals())


def event_details(request, id):
    """ Get event details of a CompanyEvent. """
    if hasattr(request, 'person') and request.is_board:
        event = get_object_or_404(CompanyEvent, id=id)
    else:
        event = get_object_or_404(CompanyEvent, id=id, visible_from__lte=timezone.now(), visible_till__gte=timezone.now())

    import icalendar
    evt = icalendar.Event()
    evt.add('dtstart', event.begin)
    evt.add('dtend', event.end)
    evt.add('summary', event.summary)

    obj = event

    return render(request, "companies/company_event.html", locals())


@require_board
def event_edit(request, id):
    """ Edit a company event. """
    obj = get_object_or_404(CompanyEvent, id=id)

    if request.method == 'POST':
        form = CompanyEventForm(instance=obj, data=request.POST)

        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = Committee.objects.get(name="Bestuur")

            event.save()
            return HttpResponseRedirect(event.get_absolute_url())
        else:
            return render(request, "companies/company_event_form.html", locals())
    else:
        form = CompanyEventForm(instance=obj)

        return render(request, "companies/company_event_form.html", locals())


@require_board
def event_delete(request, id):
    """ Delete a company event. """
    obj = get_object_or_404(CompanyEvent, id=id)

    if request.POST:
        if 'yes' in request.POST:
            obj.delete()
            return HttpResponseRedirect(reverse('companies:event_list'))
        elif 'no' in request.POST:
            return HttpResponseRedirect(obj.get_absolute_url())

    return render(request, "companies/company_confirm_delete.html", locals())


def event_list(request):
    """
    List all upcoming and 10 old CompanyEvents.

    Only if the person viewing is not a board member no event past their visible_till date will be shown.
    """
    if hasattr(request, 'person') and request.is_board:
        events = CompanyEvent.objects.all()
    else:
        events = CompanyEvent.objects.filter(visible_from__lte=timezone.now(), visible_till__gte=timezone.now())

    old_events = list(events.filter(end__lt=timezone.now()))[-10:]
    new_events = list(events.filter(end__gte=timezone.now()))

    return render(request, "companies/company_event_list.html", locals())


def event_old(request):
    """
    Returns the overview of old external activities between two dates.

    Will only show events with an visible_till date after the current time.
    """
    form = PeriodForm(to_date_required=False, data=request.GET or None)

    if form.is_valid():
        start_date = form.cleaned_data['from_date']
        end_date = form.cleaned_data['to_date'] or timezone.now()
    else:
        start_date = form.fields['from_date'].initial
        end_date = form.fields['to_date'].initial

    # Convert dates to datetimes
    start_datetime = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time()))
    end_datetime = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time()))

    events = CompanyEvent.objects.filter(end__range=(start_datetime, end_datetime), visible_till__gte=timezone.now()) \
        .order_by('-end')
    return render(request, "companies/company_event_old.html", {
        'form': form,
        'events': events,
    })


def company_events_ics(request):
    """ Will return an ics file containing all the CompanyEvents. """
    resp = HttpResponse(content_type='text/calendar; charset=UTF-8')
    resp.write(ical_calendar(_('Inter-Actief external activities'), CompanyEvent.objects.filter(
        begin__gte=timezone.now() - datetime.timedelta(100)).order_by('begin')))

    return resp


def company_event_ics(request, id):
    """ Will return an ics file containing only one single CompanyEvent. """
    event = get_object_or_404(CompanyEvent, id=id)

    resp = HttpResponse(content_type='text/calendar; charset=UTF-8')
    resp.write(ical_calendar(_(event.summary), [event, ]))

    return resp


# TODO The Audit committee should also be able to view this page, should await issue #54
class CompanyStatisticsView(RequireCommitteeMixin, FormView):
    template_name = "companies/company_statistics.html"
    form_class = StatisticsForm
    abbreviation = 'KasCo'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        end_date = timezone.datetime(timezone.now().year, ((timezone.now().month - 1) // 3) * 3 + 1, 1)

        # Hopefully guarantees to go back 3 months (last financial quarter), and not any less or further
        # Guaranteed by the fact that 2 months take a maximum of 31 + 31 = 62
        # While 3 months take a minimum of 28 + 31 + 30 = 89
        start_date = end_date - timezone.timedelta(days=65)
        start_date = start_date.replace(day=1)

        kwargs['initial'] = {
            'start_date': start_date,
            'end_date': end_date
        }

        return kwargs

    def form_valid(self, form):
        context = self.get_context_data(form=form)

        # Get statistics of period
        start = form.cleaned_data['start_date']
        end = form.cleaned_data['end_date']

        # Get overlapping company items
        context['companies'] = Company.objects.filter(
            Q(start_date__lte=start, end_date__gt=start) |
            Q(start_date__lt=end, end_date__gte=end) |
            Q(start_date__gte=start, end_date__lte=end)
        ).all()

        context['website_banners'] = WebsiteBanner.objects.filter(
            Q(start_date__lte=start, end_date__gt=start) |
            Q(start_date__lt=end, end_date__gte=end) |
            Q(start_date__gte=start, end_date__lte=end)
        ).all()

        context['television_banners'] = TelevisionBanner.objects.filter(
            Q(start_date__lte=start, end_date__gt=start) |
            Q(start_date__lt=end, end_date__gte=end) |
            Q(start_date__gte=start, end_date__lte=end)
        ).all()

        context['events'] = CompanyEvent.objects.filter(
            Q(begin__lte=start, end__gt=start) |
            Q(begin__lt=end, end__gte=end) |
            Q(begin__gte=start, end__lte=end)
        ).all()

        return self.render_to_response(context)

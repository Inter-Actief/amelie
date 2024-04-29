import re

from datetime import date
import csv

from django.urls import reverse
from django.views import View
from django.views.generic import CreateView
from functools import reduce

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import HttpResponse, Http404, HttpResponseRedirect, QueryDict
from django.shortcuts import render, redirect
from django.template import loader
from django.views.decorators.cache import never_cache
from django.utils.translation import gettext_lazy as _l

from amelie.api.models import PushNotification
from amelie.members.forms import SearchForm
from amelie.tools.forms import ExportForm
from amelie.members.models import Person, Preference, Student, Employee
from amelie.members.query_forms import MailingForm, QueryForm, PushNotificationForm
from amelie.members.tasks import send_push_notification
from amelie.tools import types
from amelie.tools.decorators import require_board
from amelie.tools.logic import current_association_year
from amelie.tools.mixins import RequireBoardMixin
from amelie.tools.paginator import RangedPaginator


@require_board
@never_cache
def query(request):
    page = types.get_int(request.GET, 'page', default=1, min_value=1)
    limit = types.get_int(request.GET, 'limit', default=25, min_value=1, max_value=999)
    search = request.GET.get('search', False)
    persons = filter_member_list(request.GET)

    # If just one hit, navigate directly to this person
    if persons.count() == 1:
        return redirect(persons[0].get_absolute_url())

    search_args = [request.GET] if not search else []
    form = QueryForm(*search_args)
    search_form = SearchForm(request.GET)
    object_list = persons.distinct()

    export_form = ExportForm()
    export_form.fields['export_details'].initial = request.GET.urlencode()

    if object_list.count() > 0:
        p = RangedPaginator(object_list, limit)

        # Pick right page
        try:
            page = p.page(page)
        except PageNotAnInteger:
            page = p.page(1)
        except EmptyPage:
            page = p.page(p.num_pages)

        # Set page range for paginator
        p.set_page_range(page, 7)

    # Done
    return render(request, 'query.html', locals())


def filter_member_list_public(qdict, count=None):
    persons = Person.objects.members()
    persons = filter_search_public(qdict, persons)
    return persons[:count] if count else persons


def filter_member_list(qdict, count=None):
    search = qdict.get('search', False)
    persons = Person.objects.all()
    persons = filter_search(qdict, persons) if search else filter_query(qdict, persons)
    return persons[:count] if count else persons


def filter_search_public(search, persons):
    """Function that searches in the member database, which is publicly usable (only searches by name)"""
    form = SearchForm(search)
    if form.is_valid():
        search = form.cleaned_data['search']
        slug_qs = reduce(lambda x, y: x & y, [Q(slug__icontains=q) for q in search.split(' ')])
        return persons.filter(slug_qs)
    else:
        return []


def filter_search(search, persons):
    """Function that searches in the member database, which does not offer public data! Board only!"""
    form = SearchForm(search)
    if form.is_valid():
        search = form.cleaned_data['search']
        slug_qs = reduce(lambda x, y: x & y, [Q(slug__icontains=q) for q in search.split(' ')])
        qs = slug_qs | Q(address__icontains=search) | Q(city__icontains=search)
        qs = qs | Q(account_name__icontains=search) | Q(email_address__icontains=search)
        try:
            nr = int(search)
            qs = qs | Q(student__number=nr)
            qs = qs | Q(employee__number=nr)
        except ValueError:
            pass
        return persons.filter(
            Q(membership__ended__gt=date.today()) | Q(membership__ended__isnull=True),
            membership__year=current_association_year()
        ).filter(qs)
    else:
        return []


def filter_query(query_dict, persons):
    query_form = QueryForm(query_dict)
    if query_form.is_valid():
        persons = query_form.filter(persons)
    else:
        # The query is invalid, so return no results
        persons = persons.none()
    return persons


@require_board
def send_mailing(request):
    persons = filter_member_list(request.GET)
    form = MailingForm(data=request.POST or None)

    if not persons:
        # No people found, give 404
        raise Http404

    # Variables are used in template, don't remove!
    longest_first_name = max([p.first_name for p in persons if p.first_name is not None], key=len)
    longest_last_name = max([p.last_name for p in persons if p.last_name is not None], key=len)
    longest_address = max([p.address for p in persons if p.address is not None], key=len)
    longest_postal_code = max([p.postal_code for p in persons if p.postal_code is not None], key=len)
    longest_city = max([p.city for p in persons if p.city is not None], key=len)
    longest_country = max([p.country for p in persons if p.country is not None], key=len)
    longest_student_number = '0123456'

    if request.method == "POST" and form.is_valid():
        if request.POST.get('preview', None):
            previews = form.build_multilang_preview(persons[0])
        else:
            task = form.build_task(persons)
            task.send()

            return render(request, 'message.html', {'message': _l(
                'The mails are now being sent one by one. This happens in a background process and might take a while.'
            )})

    return render(request, 'includes/query/query_mailing.html', locals())


class SendNotification(RequireBoardMixin, CreateView):
    model = PushNotification
    template_name = "includes/query/query_push.html"
    form_class = PushNotificationForm

    def get_context_data(self, **kwargs):
        context = super(SendNotification, self).get_context_data(**kwargs)

        persons = filter_member_list(self.request.GET)
        if not persons:
            raise Http404

        preferences = Preference.objects.filter(name='notifications')

        persons = Person.objects.filter(id__in=[x.pk for x in persons])
        persons = persons.filter(preferences__in=preferences, user__fcmdevice__isnull=False).distinct()

        context['count'] = persons.count()
        return context

    def form_valid(self, form):
        notification = form.save()

        recipients = filter_member_list(self.request.GET)
        if not recipients.exists():
            raise Http404

        notification.recipients.set(recipients)
        notification.save()

        send_push_notification.delay(notification,
                                     Person.objects.filter(id__in=[x.pk for x in recipients]),
                                     report_to=self.request.person.email_address,
                                     report_language=self.request.person.preferred_language)

        messages.info(self.request, _l(
            'The push notifications are now being sent one by one. This happens in a background process and might '
            'take a while. You will get a delivery report via e-mail when it is complete.'))

        return HttpResponseRedirect(self.request.get_full_path())


class DataExport(RequireBoardMixin, View):
    """
    View to execute a data export on a given query, and to a given format.
    This view will create a DataExportInformation object and store it before executing the export.
    """
    http_method_names = ["post"]

    @staticmethod
    def post(request):
        form = ExportForm(request.POST)
        if form.is_valid():
            # Save the data export information and retrieve the export type to determine what to do.
            dei_id, export_type = form.save_data_export_information(request.user.person)

            filter_querydict = QueryDict(form.cleaned_data['export_details'])

            if export_type == 'member_export_csv':
                return DataExport.csv_export(filter_querydict)
            elif export_type == 'member_export_vcf':
                return DataExport.vcf_export(filter_querydict)
            elif export_type == 'member_export_email':
                return DataExport.email_export(filter_querydict)
            else:
                # Redirect back to query view with an error message.
                messages.warning(request, _l(
                    "Could not make a data export, because an unknown data export type was selected."
                ))

                if 'export_details' in form.cleaned_data and form.cleaned_data['export_details']:
                    return HttpResponseRedirect(reverse('members:query') + "?" + form.cleaned_data['export_details'])
                else:
                    return HttpResponseRedirect(reverse('members:query'))

        else:
            # Redirect back to query view with an error message.
            messages.warning(request, _l(
                "Could not create data export, because something went wrong while saving information about the export."
            ))
            if form.cleaned_data and 'export_details' in form.cleaned_data and form.cleaned_data['export_details']:
                return HttpResponseRedirect(reverse('members:query') + "?" + form.cleaned_data['export_details'])
            else:
                return HttpResponseRedirect(reverse('members:query'))

    @staticmethod
    def csv_export(filter_parameters):
        persons = filter_member_list(filter_parameters)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        # Use .txt. Excel 2007 forces the wrong text encoding (not UTF-8) with .csv
        response['Content-Disposition'] = 'attachment; filename=amelie-export.txt'

        writer = csv.writer(response, dialect=csv.excel)
        writer.writerow([f.attname for f in Person._meta.fields] + ['student_number', 'employee_number'])
        for p in persons:
            extra_fields = []
            try:
                extra_fields.append(p.student.number)
            except Student.DoesNotExist:
                extra_fields.append(None)
            try:
                extra_fields.append(p.employee.number)
            except Employee.DoesNotExist:
                extra_fields.append(None)
            fields = [getattr(p, f.attname, '') for f in Person._meta.fields]

            # Remove useless whitespace from the fields
            for i, val in enumerate(fields):
                if isinstance(val, str):
                    fields[i] = re.sub(r'\s+', " ", val)
            writer.writerow(fields + extra_fields)

        return response

    @staticmethod
    def vcf_export(filter_parameters):
        persons = filter_member_list(filter_parameters)

        content = loader.render_to_string('exports/vcard.vcf', context={'persons': persons})

        # Force Windows line endings because otherwise the import does not work on the Gigaset DX800A (IA Phone).
        content = content.replace('\n', '\r\n')

        response = HttpResponse(content, content_type='text/x-vcard; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=amelie-export.vcf'
        return response

    @staticmethod
    def email_export(filter_parameters):
        persons = filter_member_list(filter_parameters)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=amelie-email-export.txt'
        writer = csv.writer(response, dialect=csv.excel)
        writer.writerow([p.email_address for p in persons])
        return response

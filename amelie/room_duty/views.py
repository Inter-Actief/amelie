from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from amelie.room_duty.forms import RoomDutyTableForm, RoomDutyPoolForm, RoomDutyTableTemplateForm, \
    RoomDutyTemplateForm, RoomDutyTableChangeForm, RoomDutyForm, RoomDutyAvailabilityForm, \
    RoomDutyParticipantForm, BalconyDutyAssociationForm
from amelie.room_duty.models import RoomDutyTable, RoomDuty, RoomDutyAvailability, RoomDutyPool, \
    RoomDutyTableTemplate, RoomDutyTemplate, BalconyDutyAssociation
from amelie.members.forms import SearchForm as MemberSearchForm
from amelie.members.models import Person
from amelie.members.query_views import filter_member_list_public
from amelie.tools.decorators import require_board
from amelie.tools.functions import DateTimeDifference
from amelie.tools.calendar import ical_calendar


@login_required
def index(request):
    if not request.person.room_duty_pools.all() and not request.is_board:
        raise PermissionDenied

    tables = RoomDutyTable.objects

    if not request.is_board:
        tables = tables.filter(unsorted_pool=request.person)

    tables = tables.order_by("-begin")

    return render(request, "room_duty/table/list.html", locals())


@require_board
def table_add(request):
    is_new = True

    last_table = initial_balcony_duty = RoomDutyTable.objects.filter(balcony_duty__isnull=False).order_by('-begin').first()
    initial = {} if last_table is None else {'balcony_duty': last_table.balcony_duty.cycle_next()}

    if request.method == 'POST':
        form = RoomDutyTableForm(request.POST, initial=initial)

        if form.is_valid():
            title, pool, begin, balcony_duty = form.cleaned_data["title"], form.cleaned_data['pool'], form.cleaned_data['begin'], form.cleaned_data['balcony_duty']
            table = RoomDutyTableTemplate.instantiate(form.cleaned_data['template'], title, pool, begin, balcony_duty)
            return redirect(reverse('room_duty:table_overview', kwargs={'pk': table.pk}))
    else:
        form = RoomDutyTableForm(initial=initial)

    return render(request, "room_duty/table/form.html", locals())


@require_board
def table_change(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    form = RoomDutyTableChangeForm(instance=table)
    room_duty_form = RoomDutyForm()

    if request.method == 'POST':
        form = RoomDutyTableChangeForm(request.POST, instance=table)

        if form.is_valid():
            form.save()
            return redirect(reverse('room_duty:table_overview', kwargs={'pk': pk}))

    return render(request, 'room_duty/table/change.html', locals())


@require_board
def table_change_persons(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    if 'search' in request.GET:
        search_form = MemberSearchForm(request.GET)

        if search_form.is_valid():
            persons = filter_member_list_public(request.GET, 25)
    else:
        search_form = MemberSearchForm()

    if request.method == 'POST':
        try:
            person = Person.objects.get(id=int(request.POST['person_id']))
            table.unsorted_pool.add(person)
            table.save()
        except (ValueError, Person.DoesNotExist):
            # Only arises when deliberately POSTing invalid data
            pass

        return redirect(reverse('room_duty:table_overview', kwargs={'pk': pk}))

    return render(request, 'room_duty/table/change_persons.html', locals())


@require_board
def table_change_persons_delete(request, pk, person_pk):
    if request.method == 'POST':
        rel = get_object_or_404(RoomDutyTable.unsorted_pool.through, person_id=person_pk, roomdutytable_id=pk)
        rel.delete()
        return redirect(reverse('room_duty:table_overview', kwargs={'pk': pk}))


@require_board
def table_delete(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    if request.method == 'POST':
        table.delete()
        return redirect(reverse('room_duty:index'))

    return render(request, 'room_duty/table/delete.html', locals())


def table_print(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    return render(request, 'room_duty/table/print.html', locals())


@require_http_methods(['POST'])
@require_board
def table_room_duty_add(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)
    form = RoomDutyForm(request.POST)

    if form.is_valid():
        room_duty = form.save(commit=False)
        room_duty.table = table
        room_duty.save()
        return redirect(reverse('room_duty:table_change', kwargs={'pk': pk}))

    return render(request, 'room_duty/table/room_duty_add.html', locals())


@require_board
def table_room_duty_delete(request, pk, room_duty_pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)
    room_duty = get_object_or_404(RoomDuty, pk=room_duty_pk)

    if room_duty.table != table:
        raise Http404

    if request.method == 'POST':
        room_duty.delete()
        return redirect(reverse('room_duty:table_change', kwargs={'pk': pk}))

    return render(request, 'room_duty/table/room_duty_delete.html', locals())


def get_stats_of_queryset(room_duties):
    room_duties = room_duties.annotate(duration=DateTimeDifference('begin', 'end'))
    no_time = timedelta(seconds=0)

    return {
        'morning': (room_duties.filter(begin__hour__lt=12).aggregate(Sum('duration'))['duration__sum'] or no_time)
            .total_seconds() / 60 / 60,
        'afternoon': (room_duties.filter(begin__hour__gte=12).aggregate(Sum('duration'))['duration__sum'] or no_time)
            .total_seconds() / 60 / 60,
        'total': (room_duties.aggregate(Sum('duration'))['duration__sum'] or no_time)
            .total_seconds() / 60 / 60
    }


@login_required
def table_overview(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    if request.person not in table.persons and not request.is_board:
        raise PermissionDenied

    room_duties = table.room_duties.prefetch_related('participant_set').all()

    for room_duty in room_duties:
        room_duty.duration = (room_duty.end - room_duty.begin).total_seconds() / 60 / 60

    # Form logic
    if request.method == 'POST':
        for room_duty in room_duties:
            participant_form = RoomDutyParticipantForm(instance=room_duty, prefix=room_duty.pk, data=request.POST)

            if participant_form.is_valid():
                participant_form.save()
            else:
                print("Got invalid form!")
                print(participant_form.errors)

        return redirect(reverse('room_duty:table_overview', kwargs={'pk': pk}))

    availability_set = RoomDutyAvailability.objects.filter(room_duty__in=room_duties,
                                                           person__in=table.persons).select_related('person', 'room_duty')
    availabilities_map = {}

    for availability in availability_set:
        availabilities_map[availability.room_duty, availability.person] = availability

    for room_duty in room_duties:
        room_duty_availabilities = [availabilities_map.get((room_duty, person), None)
                                    for person in table.persons]
        assignment = [person.pk for person in room_duty.participant_set.all()]
        participant_form = RoomDutyParticipantForm(instance=room_duty, prefix=room_duty.pk, initial={'participant_set': assignment})

        # Zip the availabilities to the checkboxes of the participant_set
        room_duty.template_data = zip(room_duty_availabilities, participant_form['participant_set'])

    # Statistics
    for person in table.persons:
        person_room_duties = RoomDuty.objects.filter(participant_set__in=[person])
        person.room_duty_stats = get_stats_of_queryset(person_room_duties)

        person_room_duties_table = person_room_duties.filter(table=table)
        person.room_duty_stats_table = get_stats_of_queryset(person_room_duties_table)

        person_room_duties_base = person_room_duties.exclude(pk__in=[room_duty.pk for room_duty in table.room_duties.all()])
        person.room_duty_stats_base = get_stats_of_queryset(person_room_duties_base)

    return render(request, 'room_duty/table/overview.html', locals())


@login_required
def table_fill(request, pk):
    table = get_object_or_404(RoomDutyTable, pk=pk)

    if request.person not in table.persons:
        raise PermissionDenied

    room_duties = table.room_duties.prefetch_related('participant_set').all()
    availabilities = []

    all_valid = True

    for room_duty in room_duties:
        availability = RoomDutyAvailability.objects.filter(room_duty=room_duty,
                                                           person=request.person).first()

        if request.method == 'POST':
            form = RoomDutyAvailabilityForm(instance=availability,
                                            prefix=room_duty.id,
                                            data=request.POST)

            if form.is_valid():
                availability = form.save(commit=False)
                availability.room_duty = room_duty
                availability.person = request.person
                availability.save()
            else:
                all_valid = False
        else:
            form = RoomDutyAvailabilityForm(instance=availability, prefix=room_duty.id)

        availabilities.append((room_duty, availability, form))

    if request.method == 'POST' and all_valid:
        return redirect(reverse('room_duty:table_overview', kwargs={'pk': pk}))

    # request.method == 'GET' or not all_valid
    return render(request, 'room_duty/table/fill.html', locals())


@require_board
def balcony_duty(request):
    associations = BalconyDutyAssociation.objects.all()

    if request.method == 'POST':
        form = BalconyDutyAssociationForm(data=request.POST)
        if form.is_valid():
            form.save()

        return redirect(reverse('room_duty:balcony_duty'))

    form = BalconyDutyAssociationForm()
    return render(request, 'room_duty/balcony_duty/balcony_duty.html', locals())


@require_board
@require_http_methods(['POST'])
def balcony_duty_up(request, pk):
    association = get_object_or_404(BalconyDutyAssociation, pk=pk)

    if association.rank == 1:
        raise PermissionDenied

    association.move_up()
    return redirect(reverse('room_duty:balcony_duty'))


@require_board
@require_http_methods(['POST'])
def balcony_duty_down(request, pk):
    association = get_object_or_404(BalconyDutyAssociation, pk=pk)

    if association.rank == BalconyDutyAssociation.count():
        raise PermissionDenied

    association.move_down()
    return redirect(reverse('room_duty:balcony_duty'))


@require_board
def balcony_duty_delete(request, pk):
    association = get_object_or_404(BalconyDutyAssociation, pk=pk)

    if request.method == 'POST':
        association.delete()
        return redirect(reverse('room_duty:balcony_duty'))

    return render(request, 'room_duty/balcony_duty/delete.html', locals())

@require_board
def pools(request):
    pools = RoomDutyPool.objects.all()

    return render(request, "room_duty/pool/list.html", locals())


@require_board
def pool_add(request):
    if request.method == 'POST':
        form = RoomDutyPoolForm(request.POST)

        if form.is_valid():
            pool = form.save()
            return redirect(reverse('room_duty:pool_change_persons', kwargs={'pk': pool.pk}))
    else:
        form = RoomDutyPoolForm()

    return render(request, "room_duty/pool/form.html", locals())


@require_board
def pool_delete(request, pk):
    pool = get_object_or_404(RoomDutyPool, pk=pk)

    if request.method == 'POST':
        pool.delete()
        return redirect(reverse('room_duty:pools'))

    return render(request, 'room_duty/pool/delete.html', locals())


@require_board
def pool_change_persons(request, pk):
    pool = get_object_or_404(RoomDutyPool, pk=pk)

    if 'search' in request.GET:
        search_form = MemberSearchForm(request.GET)

        if search_form.is_valid():
            persons = filter_member_list_public(request.GET, 25)
    else:
        search_form = MemberSearchForm()

    if request.method == 'POST':
        try:
            person = Person.objects.get(id=int(request.POST['person_id']))
            pool.unsorted_persons.add(person)
            pool.save()
        except (ValueError, Person.DoesNotExist):
            # Only arises when deliberately POSTing invalid data
            pass

        return redirect(reverse('room_duty:pool_change_persons', kwargs={'pk': pk}))

    return render(request, 'room_duty/pool/persons_change.html', locals())


@require_board
@require_http_methods(['POST'])
def pool_delete_person(request, pk, person_id):
    pool = get_object_or_404(RoomDutyPool, pk=pk)
    pool.unsorted_persons.remove(Person(id=person_id))
    pool.save()

    return redirect(reverse('room_duty:pool_change_persons', kwargs={'pk': pk}))


@require_board
def templates(request):
    templates = RoomDutyTableTemplate.objects.all()

    return render(request, 'room_duty/template/list.html', locals())


@require_board
def template_add(request):
    if request.method == 'POST':
        form = RoomDutyTableTemplateForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(reverse('room_duty:templates'))
    else:
        form = RoomDutyTableTemplateForm()

    return render(request, 'room_duty/template/add.html', locals())


@require_board
def template_change(request, pk):
    template = get_object_or_404(RoomDutyTableTemplate, pk=pk)

    form = RoomDutyTableTemplateForm(instance=template)
    room_duty_form = RoomDutyTemplateForm()

    if request.method == 'POST':
        form = RoomDutyTableTemplateForm(request.POST, instance=template)

        if form.is_valid():
            form.save()
            return redirect(reverse('room_duty:template_change', kwargs={'pk': pk}))

    return render(request, 'room_duty/template/change.html', locals())


@require_board
def template_delete(request, pk):
    template = get_object_or_404(RoomDutyTableTemplate, pk=pk)

    if request.method == 'POST':
        template.delete()
        return redirect(reverse('room_duty:templates'))

    return render(request, 'room_duty/template/delete.html', locals())


@require_http_methods(['POST'])
@require_board
def template_room_duty_add(request, pk):
    template = get_object_or_404(RoomDutyTableTemplate, pk=pk)
    form = RoomDutyTemplateForm(request.POST)

    if form.is_valid():
        room_duty = form.save(commit=False)
        room_duty.table = template
        room_duty.save()
        return redirect(reverse('room_duty:template_change', kwargs={'pk': pk}))
    else:
        return render(request, 'room_duty/template/room_duty_add.html', locals())


@require_http_methods(['POST'])
@require_board
def template_room_duty_delete(request, pk, room_duty_pk):
    template = get_object_or_404(RoomDutyTableTemplate, pk=pk)
    room_duty = get_object_or_404(RoomDutyTemplate, pk=room_duty_pk)

    if room_duty.table != template:
        raise Http404

    room_duty.delete()
    return redirect(reverse('room_duty:template_change', kwargs={'pk': pk}))


def room_duty_ics(request, pk):
    person = get_object_or_404(Person, pk=pk)

    cal = ical_calendar("Room Duty IA", person.room_duties.all())
    return HttpResponse(cal, content_type='text/calendar; charset=UTF-8')

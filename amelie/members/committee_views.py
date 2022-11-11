from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import get_list_or_404, render, get_object_or_404
from django.utils import timezone

from amelie.activities.models import Activity
from amelie.members.forms import CommitteeForm, CommitteeMemberForm, SaveNewFirstModelFormSet
from amelie.members.models import CommitteeCategory, Committee, Function
from amelie.tools.decorators import require_board
from amelie.tools.calendar import ical_calendar


def committees(request):
    categories = get_list_or_404(CommitteeCategory)
    committees_without_category = Committee.objects.filter(category__isnull=True).filter(abolished__isnull=True)
    committees_abolished = Committee.objects.filter(abolished__isnull=False)
    is_board = hasattr(request, 'person') and request.is_board
    return render(request, 'committees.html', locals())


def committee(request, id, slug):
    obj = get_object_or_404(Committee, id=id, slug=slug)
    is_board = hasattr(request, 'person') and getattr(request, 'is_board', False)

    members = obj.function_set.filter(end__isnull=True).order_by('person')

    is_committee_member = hasattr(request, 'person') and (request.person in [m.person for m in members])

    if ((not obj.category) or (obj.abolished and not is_committee_member)) and not (is_board or is_committee_member):
        raise PermissionDenied

    activities = Activity.objects.filter_public(request).filter(organizer=obj, end__gte=timezone.now())
    past_activities = Activity.objects.distinct().filter(organizer=obj, end__lt=timezone.now(), photos__gt=0,
                                                         photos__public=True).order_by('-end')[:3]

    # Old-members, also from parent committees
    committees = Committee.objects.filter(Q(pk=obj.id) | Q(pk__in=[x.pk for x in obj.parent_committees.all()]))
    filter = Q(end__isnull=False, committee__abolished__isnull=True) | Q(committee__abolished__isnull=False)
    old_members = Function.objects.filter(filter, committee__in=committees).select_related('committee',
                                                                                           'person').order_by('-end')

    numbers = getattr(request, 'is_board', False) or (
        hasattr(request, 'person') and is_committee_member and not obj.abolished
    )

    return render(request, "committee.html", locals())


def committee_agenda_ics(request, id, slug):
    obj = get_object_or_404(Committee, id=id, slug=slug)

    resp = HttpResponse(content_type='text/calendar; charset=UTF-8')
    resp.write(ical_calendar(obj, obj.event_set.all()))
    return resp


def committee_random_picture(request, id, slug):
    committee = get_object_or_404(Committee, pk=id, slug=slug)
    activity_filters = Q(photos__gt=0)
    picture_filters = Q()

    # Construct filters
    if not hasattr(request, 'person'):
        activity_filters = Q(photos__public=True)
        picture_filters = Q(public=True)

    # Also get random pictures from parent committees
    if committee.parent_committees.count() > 0:
        committees = Committee.objects.filter(parent_committees__in=committee.parent_committees.all())
        activity_filters = Q(organizer__in=committees) & activity_filters
    else:
        activity_filters = Q(organizer=committee) & activity_filters

    activity = Activity.objects.filter_public(request).filter(activity_filters).order_by('?').first()
    picture = None

    if activity:
        picture = activity.photos.filter(picture_filters).order_by('?').first()

    if not activity or not picture:
        raise Http404

    # Done
    return picture.to_http_response(format='small', response='json')


@require_board
def committee_new(request):
    form = CommitteeForm() if request.method != "POST" else CommitteeForm(request.POST)

    if request.method == "POST" and form.is_valid():
        committee = form.save()
        return HttpResponseRedirect(committee.get_absolute_url())

    return render(request, 'committee_form.html', {'form': form, 'is_new': True})


@require_board
def committee_edit(request, id, slug):
    obj = get_object_or_404(Committee, pk=id, slug=slug)
    form = CommitteeForm(instance=obj, data=request.POST or None, files=request.FILES or None)

    if request.method == "POST" and form.is_valid():
        obj = form.save()
        return HttpResponseRedirect(obj.get_absolute_url())

    return render(request, 'committee_form.html', {'form': form, 'is_new': False})


@require_board
def committee_members_edit(request, id, slug):
    obj = get_object_or_404(Committee, pk=id, slug=slug)
    FunctionFormSet = inlineformset_factory(Committee, Function, form=CommitteeMemberForm, extra=10, can_delete=False,
                                            formset=SaveNewFirstModelFormSet)
    formset = FunctionFormSet(instance=obj, queryset=obj.function_set.filter(end__isnull=True))
    if request.method == "POST":
        formset = FunctionFormSet(request.POST, instance=obj, queryset=obj.function_set.filter(end__isnull=True))
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(obj.get_absolute_url())

    return render(
        request, 'committee_edit_members.html', {'id': id, 'slug': slug, 'committee': obj, 'formset': formset}
    )


@require_board
def committee_single_member_edit(request, id, slug, function_id):
    obj = get_object_or_404(Function, pk=function_id)
    function_form = CommitteeMemberForm(instance=obj)
    if request.method == "POST":
        function_form = CommitteeMemberForm(request.POST, instance=obj)
        if function_form.is_valid():
            function_form.save()
            return HttpResponseRedirect(obj.committee.get_absolute_url())

    return render(
        request, 'committee_edit_single_member.html', {'id': id, 'slug': slug, 'committee': obj.committee, 'function': obj, 'form': function_form}
    )

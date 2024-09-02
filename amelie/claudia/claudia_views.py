from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, View, TemplateView
from django.views.generic.edit import UpdateView, CreateView, DeleteView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.utils.translation import ugettext_lazy as _l

from amelie.settings import SYSADMINS_ABBR
from amelie.tools.mixins import RequireCommitteeMixin, RequireStrictCommitteeMixin

from amelie.claudia.forms import SearchMappingForm, PersonalAliasCreateForm
from amelie.claudia.models import Mapping, CLAUDIA_GROUP_POSTFIX, Membership, ExtraGroup, ExtraPerson, \
    AliasGroup, Contact, Timeline, SharedDrive, ExtraPersonalAlias


##
# Claudia home page
##
class ClaudiaHome(RequireCommitteeMixin, TemplateView):
    template_name = 'claudia/home.html'
    abbreviation = SYSADMINS_ABBR


###
# Mapping views
###
class MappingList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    model = Mapping
    paginate_by = 50

    def get_queryset(self):
        q = super(MappingList, self).get_queryset()

        form = SearchMappingForm(self.request.GET)
        if form.is_valid():
            cleaned_data = form.cleaned_data

            if cleaned_data['search']:
                search = cleaned_data['search']
                q = q.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(adname__icontains=search))
            if cleaned_data['types']:
                q = q.filter(type__in=cleaned_data['types'])
            if not cleaned_data['include_inactive']:
                q = q.filter(active=True)

        return q

    def get_context_data(self, **kwargs):
        c = super(MappingList, self).get_context_data(**kwargs)
        c['form'] = SearchMappingForm(self.request.GET)
        query = self.request.GET.copy()
        if query.get('page'):
            query.pop('page')
        c['query'] = query.urlencode()
        return c


class MappingDetailView(RequireCommitteeMixin, DetailView):
    abbreviation = SYSADMINS_ABBR
    queryset = Mapping.objects.all()

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(MappingDetailView, self).get_context_data(**kwargs)

        obj = context['object'].get_mapped_object()

        # Add in the extra data
        context['auto_members'] = [Mapping.wrap(o) for o in obj.members()]
        context['extra_members'] = context['object'].extra_members.all()
        context['auto_groups'] = [Mapping.wrap(o) for o in obj.groups()]
        context['extra_groups'] = context['object'].extra_groupmemberships.all()

        return context


class AddToMappingList(RequireCommitteeMixin, View):
    abbreviation = SYSADMINS_ABBR

    def post(self, request, pk):
        pk = int(pk)
        mapping = get_object_or_404(Mapping, id=pk)
        search = request.POST['search']
        results = Mapping.objects.filter(name__icontains=search).exclude(
            extra_groupmemberships__group=mapping).order_by('-active', 'name')
        context = {'mapping': mapping, 'results': results}
        return render(request, "claudia/add_to_mapping_list.html", context)


class AddMappingToList(RequireCommitteeMixin, View):
    abbreviation = SYSADMINS_ABBR

    def post(self, request, pk):
        pk = int(pk)
        mapping = get_object_or_404(Mapping, id=pk)

        search = request.POST['search']

        results = Mapping.objects.filter(name__icontains=search, type__endswith=CLAUDIA_GROUP_POSTFIX).exclude(
            extra_members__member=mapping).order_by('-active', 'name')

        context = {'mapping': mapping, 'results': results}

        return render(request, "claudia/add_mapping_to_list.html", context)


class AddToMappingView(RequireCommitteeMixin, View):
    """
    :type group: Mapping
    :type member: (Mapping|str)
    """
    abbreviation = SYSADMINS_ABBR

    def __init__(self):
        super(AddToMappingView, self).__init__()
        self.group = None
        self.member = None

    def dispatch(self, request, *args, **kwargs):
        pk = int(kwargs['pk'])
        self.group = get_object_or_404(Mapping, id=pk)

        # If we have a member_id in our kwargs, search for a mapping with the given ID
        if 'member_id' in kwargs:
            member_id = int(kwargs['member_id'])
            self.member = get_object_or_404(Mapping, id=member_id)

            if Membership.objects.filter(member=self.member, group=self.group).exists():
                raise Http404('Already a member')

        return super(AddToMappingView, self).dispatch(request, args, kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, "claudia/add_to_mapping_confirm.html", {'member': self.member, 'group': self.group})

    def post(self, request, *args, **kwargs):
        if 'yes' in request.POST:
            # If the member is a Mapping, add the mapping to the group
            if isinstance(self.member, Mapping):
                if self.group.is_shareddrive() and len(self.group.members()) >= 99:
                    raise ValueError(_l("A Shared Drive can have a maximum of 99 members."))
                Membership(member=self.member, group=self.group, ad=True, mail=True, description='').save()

            else:
                raise ValueError

            return redirect(self.group)

        elif 'no' in request.POST:
            return redirect(self.group)

        return self.get(request)


class MappingVerify(RequireCommitteeMixin, View):
    abbreviation = SYSADMINS_ABBR

    def __init__(self):
        super(MappingVerify, self).__init__()
        self.mapping = None

    def dispatch(self, request, *args, **kwargs):
        pk = int(kwargs['pk'])
        self.mapping = get_object_or_404(Mapping, id=pk)
        return super(MappingVerify, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        from amelie.claudia.tasks import verify_mapping
        verify_mapping.delay(self.mapping.id)
        return redirect(self.mapping.get_absolute_url())


class MappingFind(RequireCommitteeMixin, View):
    """
    :type ident: int
    :type obj: object
    :type mapping: Mapping
    """
    abbreviation = SYSADMINS_ABBR

    def __init__(self):
        super(MappingFind, self).__init__()
        self.ident = -1
        self.obj = None
        self.mapping = None

    def dispatch(self, request, *args, **kwargs):
        if 'ident' in kwargs and 'obj_type' in kwargs and 'ident' in kwargs:
            self.ident = int(kwargs['ident'])

            try:
                self.obj = Mapping.get_object_from_mapping(kwargs['obj_type'], kwargs['ident'])
            except ObjectDoesNotExist:
                raise Http404
        else:
            raise Http404

        self.mapping = Mapping.find(self.obj)
        if self.mapping:
            return redirect(self.mapping.get_absolute_url())

        return super(MappingFind, self).dispatch(request, args, kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, "claudia/mapping_no_mapping.html", {'obj': self.obj})

    def post(self, request, *args, **kwargs):
        if 'create_mapping' in request.POST:
            mp = Mapping.create(self.obj)
            return redirect(mp.get_absolute_url())
        else:
            return self.get(request)


##
# Extra groups
##
class ExtraGroupList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 100
    model = ExtraGroup



class ExtraGroupAdd(RequireStrictCommitteeMixin, CreateView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraGroup
    fields = ['name', 'active', 'email', 'adname', 'dogroup', 'description', 'gitlab']


class ExtraGroupDetail(RequireStrictCommitteeMixin, UpdateView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraGroup
    fields = ['name', 'active', 'email', 'adname', 'dogroup', 'description', 'gitlab']


##
# Shared Drives
##
class SharedDriveList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 100
    model = SharedDrive


class SharedDriveAdd(RequireStrictCommitteeMixin, CreateView):
    abbreviation = SYSADMINS_ABBR
    model = SharedDrive
    fields = ['name', 'description']


class SharedDriveDetail(RequireStrictCommitteeMixin, UpdateView):
    abbreviation = SYSADMINS_ABBR
    model = SharedDrive
    fields = ['name', 'description']


##
# Extra persons
##
class ExtraPersonList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 100
    model = ExtraPerson


class ExtraPersonAdd(RequireStrictCommitteeMixin, CreateView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraPerson
    fields = ['name', 'active', 'email', 'adname', 'description']


class ExtraPersonDetail(RequireStrictCommitteeMixin, UpdateView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraPerson
    fields = ['name', 'active', 'email', 'adname', 'description']


##
# Alias groups
##
class AliasGroupList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 100
    model = AliasGroup


class AliasGroupAdd(RequireCommitteeMixin, CreateView):
    abbreviation = SYSADMINS_ABBR
    model = AliasGroup
    fields = ['name', 'active', 'email', 'description', 'open_to_signup']


class AliasGroupDetail(RequireCommitteeMixin, UpdateView):
    abbreviation = SYSADMINS_ABBR
    model = AliasGroup
    fields = ['name', 'active', 'email', 'description', 'open_to_signup']


##
# Contacts
##
class ContactList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 100
    model = Contact


class ContactAdd(RequireCommitteeMixin, CreateView):
    abbreviation = SYSADMINS_ABBR
    model = Contact
    fields = ['name', 'active', 'email', 'description']


class ContactDetail(RequireCommitteeMixin, UpdateView):
    abbreviation = SYSADMINS_ABBR
    model = Contact
    fields = ['name', 'active', 'email', 'description']


###
#
###
class EmailDetail(RequireCommitteeMixin, TemplateView):
    abbreviation = SYSADMINS_ABBR
    template_name = "claudia/email_detail.html"

    def get_context_data(self, **kwargs):
        context = super(EmailDetail, self).get_context_data(**kwargs)
        context['email'] = self.kwargs['email']
        context['mappings'] = Mapping.objects.filter(email=self.kwargs['email'])
        return context


##
# Delete something
##
class LinkDelete(RequireCommitteeMixin, View):
    abbreviation = SYSADMINS_ABBR
    http_method_names = ['get', 'post']

    def __init__(self):
        self.object = None
        super(LinkDelete, self).__init__()

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(Membership, id=kwargs['link_id'])
        return super(LinkDelete, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, "claudia/confirm_delete.html", {"member": self.object.member, "group": self.object.group})

    def post(self, request, *args, **kwargs):
        group = self.object.group
        if 'yes' in request.POST:
            self.object.delete()
        return redirect(group)


##
# Timelines
##
class TimelineList(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    model = Timeline
    paginate_by = 50


class MappingTimeline(RequireCommitteeMixin, SingleObjectMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    paginate_by = 50
    template_name = "claudia/mapping_timeline.html"

    def __init__(self):
        super(MappingTimeline, self).__init__()
        self.object = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(queryset=Mapping.objects.all())
        return super(MappingTimeline, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MappingTimeline, self).get_context_data(**kwargs)
        context['mapping'] = self.object
        return context

    def get_queryset(self):
        return self.object.timeline_set.all()


class PersonalAliasAddView(RequireStrictCommitteeMixin, FormView):
    abbreviation = SYSADMINS_ABBR
    form_class = PersonalAliasCreateForm
    template_name = "claudia/extrapersonalalias_form.html"

    def form_valid(self, form):
        obj = get_object_or_404(Mapping, pk=self.kwargs['pk'])
        ExtraPersonalAlias.objects.create(mapping=obj, email=form.cleaned_data['email'])
        return super(PersonalAliasAddView, self).form_valid(form)

    def get_success_url(self):
        return reverse_lazy('claudia:personal_alias', kwargs={'pk': self.kwargs['pk']})



class PersonalAliasRemoveView(RequireStrictCommitteeMixin, DeleteView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraPersonalAlias
    template_name = "claudia/extrapersonalalias_delete.html"

    def get_delete_message(self):
        return _l('Alias %(object)s has been removed' % {'object': self.get_object()})

    def get_success_url(self):
        pa = get_object_or_404(ExtraPersonalAlias, pk=self.kwargs['pk'])
        mp = pa.mapping
        return reverse_lazy('claudia:personal_alias', kwargs={'pk': mp.pk})



class PersonalAliasView(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraPersonalAlias
    paginate_by = 50

    def get_context_data(self, *, object_list=None, **kwargs):
        mapping = get_object_or_404(Mapping, pk=self.kwargs['pk'])
        kwargs = super(PersonalAliasView, self).get_context_data()
        kwargs['object'] = mapping
        return kwargs

    def get_queryset(self):
        mapping = get_object_or_404(Mapping, pk=self.kwargs['pk'])
        return ExtraPersonalAlias.objects.filter(mapping=mapping)

class PersonalAliasListView(RequireCommitteeMixin, ListView):
    abbreviation = SYSADMINS_ABBR
    model = ExtraPersonalAlias
    paginate_by = 50


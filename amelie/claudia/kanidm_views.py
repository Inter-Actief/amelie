from django.views.generic import TemplateView

from amelie.claudia.kanidm import KanidmAPI
from amelie.settings import SYSADMINS_ABBR
from amelie.tools.mixins import RequireStrictCommitteeMixin



class KanidmHome(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/home.html'
    abbreviation = SYSADMINS_ABBR



class KanidmPersonList(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/person_list.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super(KanidmPersonList, self).get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['show_system'] = self.request.GET.get('show_system', '').lower() in ['true', 't', '1']
        c['objs'] = [obj for obj in kanidm.list_persons() if c['show_system'] or not obj.is_system]
        return c


class KanidmPersonDetail(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/person_detail.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['obj'] = kanidm.get_person(self.kwargs['uuid'])
        return c


class KanidmServiceAccountList(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/service_account_list.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super(KanidmServiceAccountList, self).get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['show_system'] = self.request.GET.get('show_system', '').lower() in ['true', 't', '1']
        c['objs'] = [obj for obj in kanidm.list_service_accounts() if c['show_system'] or not obj.is_system]
        return c


class KanidmServiceAccountDetail(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/service_account_detail.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['obj'] = kanidm.get_service_account(self.kwargs['uuid'])
        return c



class KanidmGroupList(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/group_list.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super(KanidmGroupList, self).get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['show_system'] = self.request.GET.get('show_system', '').lower() in ['true', 't', '1']
        c['objs'] = [obj for obj in kanidm.list_groups() if c['show_system'] or not obj.is_system]
        return c


class KanidmGroupDetail(RequireStrictCommitteeMixin, TemplateView):
    template_name = 'claudia/kanidm/group_detail.html'
    abbreviation = SYSADMINS_ABBR

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        kanidm = KanidmAPI()
        c['obj'] = kanidm.get_group(self.kwargs['uuid'])
        return c

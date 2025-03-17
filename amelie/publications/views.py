from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView

from .models import Publication
from .forms import PublicationForm

from amelie.members.models import Committee
from amelie.tools.mixins import RequireCommitteeMixin


class PublicationList(ListView):
    template_name = "publications/publications.html"
    model = Publication
    paginate_by = 12

    def get_queryset(self):
        if self.request.april_active:
            return self.model.objects.filter_public(self.request).order_by("?")
        else:
            return self.model.objects.filter_public(self.request)

    def get_context_data(self, **kwargs):
        context = super(PublicationList, self).get_context_data(**kwargs)
        if hasattr(self.request, 'person'):
            person = self.request.person
            vivat = Committee.objects.get(abbreviation="Vivat", abolished__isnull=True)
            can_create = person.is_board() or person in vivat.members() or person.user.is_superuser
            context['can_create'] = can_create

        return context


class PublicationCreate(RequireCommitteeMixin, CreateView):
    model = Publication
    template_name = "publications/publication_form.html"
    form_class = PublicationForm
    abbreviation = "Vivat"
    success_url = reverse_lazy('publications:list_publications')

    def get_form(self, form_class=None):
        form = super(PublicationCreate, self).get_form(form_class=form_class)
        return form

    def get_context_data(self, **kwargs):
        context = super(PublicationCreate, self).get_context_data(**kwargs)
        context['is_new'] = True
        return context

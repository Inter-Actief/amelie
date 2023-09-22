from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView

from amelie.activities.forms import ActivityForm
from amelie.activities.models import Activity
from amelie.iamailer import MailTask
from amelie.iamailer.mailer import render_mail
from amelie.news.forms import NewsItemBoardForm
from amelie.news.models import NewsItem
from amelie.members.models import Preference, Person
from amelie.tools.decorators import require_board
from amelie.tools.mail import PersonRecipient
from amelie.tools.mixins import RequireBoardMixin
from amelie.weekmail.forms import WeekMailForm
from amelie.weekmail.models import WeekMail, WeekMailNewsArticle


class WeekMailWizard(RequireBoardMixin, DetailView):
    model = WeekMail
    template_name_suffix = '_wizard'


class WeekMailCreateView(RequireBoardMixin, CreateView):
    model = WeekMail
    form_class = WeekMailForm

    def get_success_url(self):
        return reverse('weekmail:wizard', args=[self.object.pk])

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.writer = self.request.person

        return super(WeekMailCreateView, self).form_valid(form)


class WeekMailUpdateView(RequireBoardMixin, UpdateView):
    model = WeekMail
    form_class = WeekMailForm

    def get_success_url(self):
        return reverse('weekmail:wizard', args=[self.object.pk])


class WeekMailListView(ListView):
    model = WeekMail

    def get_queryset(self):
        return WeekMail.objects.all().order_by('-pk') if hasattr(self.request, "is_board") and self.request.is_board else WeekMail.objects.filter(published=True).order_by('-pk')


class WeekMailPreview(DetailView):
    model = WeekMail
    template_name = "weekmail/weekmail_preview.html"

    @xframe_options_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(WeekMailPreview, self).dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if self.kwargs.get("lang", False):
            translation.activate(self.kwargs["lang"])

        weekmail = self.get_object()
        template = get_template("weekmail/weekmail_mail.mail")

        old_language = translation.get_language()
        if self.kwargs.get("lang", False):
            translation.activate(self.kwargs["lang"])

        try:
            content, subject, attachments = render_mail(template=template,
                                                        context={'weekmail': weekmail},
                                                        html=True,
                                                        preview=True)
        finally:
            translation.activate(old_language)

        context['content'] = content

        return super(WeekMailPreview, self).render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super(WeekMailPreview, self).get_context_data(**kwargs)
        context['preview'] = True
        return context


class WeekMailNewsArticleDeleteView(RequireBoardMixin, DeleteView):
    model = WeekMailNewsArticle

    def get_success_url(self):
        return reverse('weekmail:wizard', kwargs={"pk": self.kwargs["pk1"]})


class WeekMailNewsArticleUpdateView(RequireBoardMixin, UpdateView):
    model = WeekMailNewsArticle
    fields = ['title_nl', 'title_en', 'content_nl', 'content_en']

    def get_success_url(self):
        return reverse('weekmail:wizard', kwargs={"pk": self.kwargs["pk1"]})


class WeekMailNewsArticleCreateView(RequireBoardMixin, CreateView):
    model = WeekMailNewsArticle
    fields = ['title_nl', 'title_en', 'content_nl', 'content_en']

    def form_valid(self, form):
        self.object = form.save(commit=False)

        weekmailobject = WeekMail.objects.get(pk=self.kwargs["pk"])
        self.object.save()

        weekmailobject.added_news_articles.add(self.object)

        return HttpResponseRedirect(reverse('weekmail:wizard', args=(self.kwargs["pk"],)))

    def get_context_data(self, **kwargs):
        context = super(WeekMailNewsArticleCreateView, self).get_context_data(**kwargs)
        context['is_new'] = True
        return context


class NewsArticleUpdateView(RequireBoardMixin, UpdateView):
    model = NewsItem
    form_class = NewsItemBoardForm
    template_name = "news_item_form.html"

    def get_success_url(self):
        return reverse('weekmail:wizard', kwargs={"pk": self.kwargs["pk1"]})


class ActivityUpdateView(RequireBoardMixin, UpdateView):
    model = Activity
    form_class = ActivityForm
    template_name = "activities/activity_form.html"

    def get_form_kwargs(self):
        kwargs = super(ActivityUpdateView, self).get_form_kwargs()
        kwargs["person"] = self.request.person
        return kwargs

    def get_success_url(self):
        return reverse('weekmail:wizard', kwargs={"pk": self.kwargs["pk1"]})


@require_board
@require_POST
def send_weekmail(request, pk):
    weekmail = get_object_or_404(WeekMail, pk=pk)
    preference_weekmail = get_object_or_404(Preference, name="mail_association_html")
    preference_mastermail = get_object_or_404(Preference, name="mail_master")
    preference_educationalmail = get_object_or_404(Preference, name="mail_educational")

    if weekmail.mailtype == WeekMail.MailTypes.WEEKMAIL:
        persons = set(Person.objects.members().filter(preferences__id=preference_weekmail.id))
    elif weekmail.mailtype == WeekMail.MailTypes.MASTERMAIL:
        persons = set(Person.objects.members().filter(preferences__id=preference_mastermail.id))
    elif weekmail.mailtype == WeekMail.MailTypes.EDUCATION_MAIL:
        persons = set(Person.objects.members().filter(preferences__id=preference_educationalmail.id))

    # Add people who forcefully want the master or weekmail
    preference_weekmail_force = get_object_or_404(Preference, name="mail_association_html_force")
    preference_mastermail_force = get_object_or_404(Preference, name="mail_master_force")
    preference_educationalmail_force = get_object_or_404(Preference, name="mail_educational_force")

    if weekmail.mailtype == WeekMail.MailTypes.WEEKMAIL:
        persons |= set(Person.objects.filter(preferences__id=preference_weekmail_force.id))
    elif weekmail.mailtype == WeekMail.MailTypes.MASTERMAIL:
        persons |= set(Person.objects.filter(preferences__id=preference_mastermail_force.id))
    elif weekmail.mailtype == WeekMail.MailTypes.EDUCATION_MAIL:
        persons |= set(Person.objects.filter(preferences__id=preference_educationalmail_force.id))

    task = MailTask(template_name='weekmail/weekmail_mail.mail',
                    report_to=weekmail.writer.email_address,
                    report_language=weekmail.writer.preferred_language,
                    report_always=True)

    # If debug is enabled, add a single recipient, the person themselves
    if settings.DEBUG:
        task.add_recipient(PersonRecipient(request.person, context={'weekmail': weekmail}))
        print(persons)
    else:
        for person in persons:
            task.add_recipient(PersonRecipient(person, context={'weekmail': weekmail}))

    task.send()

    weekmail.published = True
    weekmail.save()

    messages.info(request, _('{} is being sent'.format(weekmail)))

    return HttpResponseRedirect(reverse('weekmail:wizard', kwargs={"pk": pk}))

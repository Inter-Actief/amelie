import random

from django.conf import settings
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.db.models import Q, Prefetch
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from amelie.iamailer.mailtask import MailTask, Recipient
from amelie.news.models import NewsItem
from amelie.members.models import Committee, Person
from amelie.education import utils
from amelie.education.forms import DEANominationForm, DEAVoteForm, ComplaintForm, ComplaintCommentForm, \
    EducationalBouquetForm, PageForm, SearchSummariesForm, CategoryForm, CourseForm, EducationEventForm, ModuleForm
from amelie.education.models import Complaint, ComplaintComment, Page, Course, Category, EducationEvent, Module
from amelie.statistics.decorators import track_hits
from amelie.tools.decorators import require_education, require_lid
from amelie.tools.mixins import RequireMemberMixin
from amelie.tools.paginator import RangedPaginator
from amelie.about.models import Page as AboutPage


@require_education
def category_edit(request, category_id):
    obj = get_object_or_404(Category, id=category_id)
    form = CategoryForm(instance=obj) if request.method != "POST" else CategoryForm(request.POST, instance=obj)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        return redirect("education:overview")
    return render(request, 'category_edit.html', locals())


@require_education
def category_delete(request, category_id):
    get_object_or_404(Category, id=category_id).delete()
    return redirect("education:overview")


@require_education
def category_new(request):
    form = CategoryForm() if request.method != "POST" else CategoryForm(request.POST)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        return redirect("education:overview")
    return render(request, 'category_new.html', locals())


@require_education
def page_edit(request, page_id):
    obj = get_object_or_404(Page, id=page_id)
    form = PageForm(instance=obj) if request.method != "POST" else PageForm(request.POST, instance=obj)
    if request.method == "POST" and form.is_valid():
        page = form.save()
        return redirect(page.get_absolute_url())
    return render(request, 'educationpage_edit.html', locals())


@require_education
def page_delete(request, page_id):
    get_object_or_404(Page, id=page_id).delete()
    return redirect('education:overview')


@require_education
def page_new(request):
    form = PageForm() if request.method != "POST" else PageForm(request.POST)
    if request.method == "POST" and form.is_valid():
        page = form.save()
        return redirect(page.get_absolute_url())
    return render(request, 'educationpage_new.html', locals())


@require_http_methods(["POST"])
@require_education
def page_up(request, page_id):
    obj = get_object_or_404(Page, id=page_id)
    obj.move_up()
    return redirect('education:overview')


@require_http_methods(["POST"])
@require_education
def page_down(request, page_id):
    obj = get_object_or_404(Page, id=page_id)
    obj.move_down()
    return redirect('education:overview')


@track_hits("Education Information")
def overview(request):
    is_board = hasattr(request, 'person') and request.is_board
    categories = []
    if request.april_active:
        for category in Category.objects.all().order_by("?"):
            categories.append((category, Page.objects.filter(category=category).order_by("?")))
        pages = Page.objects.all().order_by("?")
    else:
        for category in Category.objects.all():
            categories.append((category, Page.objects.filter(category=category)))
        pages = Page.objects.all()
    is_education = hasattr(request, 'person') and request.is_education_committee
    return render(request, 'overview.html', locals())


def news_archive(request):
    oc = Committee.education_committee()
    if request.april_active:
        education_news_list = NewsItem.objects.filter(publisher=oc).order_by("?")
    else:
        education_news_list = NewsItem.objects.filter(publisher=oc)

    # pagination things
    pages = RangedPaginator(education_news_list, 12)
    page = request.GET.get('page')

    try:
        education_news = pages.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        education_news = pages.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        education_news = pages.page(pages.num_pages)

    pages.set_page_range(education_news, 7)

    return render(request, 'education_news.html', locals())


def educational_bouquet(request):
    bouquet_form = EducationalBouquetForm()
    try:
        prev_bouquets = AboutPage.objects.get(id=22)
    except AboutPage.DoesNotExist:
        prev_bouquets = None

    is_education = hasattr(request, 'person') and request.is_education_committee

    # Temporary disable of the form submission, due to spam flooding because the form has no captcha.
    messages.warning(request, "The educational bouquet form is currently closed for submissions.")
    #if request.POST:
    #    bouquet_form = EducationalBouquetForm(request.POST)

    #    if bouquet_form.is_valid():
    #        bouquet_form.save()
    #        message_sent = True

    return render(request, 'educational_bouquet.html', locals())


def awards(request):
    try:
        awards_info = AboutPage.objects.get(id=23)
    except AboutPage.DoesNotExist:
        awards_info = None
    is_education = hasattr(request, 'person') and request.is_education_committee

    return render(request, 'awards.html', locals())


def summaries(request):
    form = SearchSummariesForm()

    if request.method == "GET":
        form = SearchSummariesForm(request.GET)
        if form.is_valid():
            courses = utils.summaries_get_courses(form.cleaned_data['filter'])
    else:
        courses = utils.summaries_get_courses()

    return render(request, 'summaries.html', locals())


def dea_nomination(request):
    dea_form = DEANominationForm()
    if request.POST:
        dea_form = DEANominationForm(request.POST)
        if dea_form.is_valid():
            dea_form.save()
            return redirect('education:overview')
    return render(request, 'dea_nomination.html', locals())


@require_lid
def dea_vote(request):
    dea_form = DEAVoteForm(request.person)
    if request.POST:
        dea_form = DEAVoteForm(request.person, request.POST)
        if dea_form.is_valid():
            dea_form.save()
            return redirect('education:overview')
    return render(request, 'dea_vote.html', locals())


@require_lid
def complaints(request):
    if request.method == "POST":  # check if people agree with a complaint or withdraw from the complaint
        complaint_id = request.POST['complaint_id']
        if complaint_id:
            complaint_obj = get_object_or_404(Complaint, id=complaint_id)
            if request.person in complaint_obj.people.all() and 'nosupport' in request.POST:
                complaint_obj.people.remove(request.person)
            elif 'support' in request.POST:
                complaint_obj.people.add(request.person)
            complaint_obj.save()

    if request.is_education_committee:
        complaint_comment_filter = Q()
    else:
        complaint_comment_filter = Q(public=True) | Q(person=request.person)

    if request.april_active:
        complaint_objs = Complaint.objects.order_by("?").exclude(subject=Complaint.ComplaintChoices.GRADING.value)\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')
        expired = Complaint.objects.filter(completed=False, subject=Complaint.ComplaintChoices.GRADING.value).order_by("?")\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')
        completed = Complaint.objects.filter(completed=True).order_by("?")\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')
    else:
        complaint_objs = Complaint.objects.filter(completed=False).exclude(subject=Complaint.ComplaintChoices.GRADING.value)\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')
        expired = Complaint.objects.filter(completed=False, subject=Complaint.ComplaintChoices.GRADING.value)\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')
        completed = Complaint.objects.filter(completed=True)\
            .prefetch_related(Prefetch('complaintcomment_set', queryset=ComplaintComment.objects.filter(complaint_comment_filter)))\
            .prefetch_related('people').prefetch_related('course')

    if not request.is_education_committee:  # power to the correct people
        reporter_q = Q(public=True) | (Q(reporter=request.person))
        complaint_objs = complaint_objs.filter(reporter_q)
        expired = expired.filter(reporter_q)
        completed = completed.filter(reporter_q)

    # Fix TypeError("Cannot filter a query once a slice has been taken.")
    if request.april_active:
        complaint_objs = complaint_objs[:random.randint(1,5)]

    return render(request, "complaints.html", locals())


@require_lid
def complaint(request, complaint_id):
    obj = get_object_or_404(Complaint, id=complaint_id)
    comment_form = ComplaintCommentForm()
    reporter = obj.reporter == request.person
    anonymous = obj.anonymous and not request.is_board

    if not obj.public and not (reporter or request.is_education_committee):
        raise Http404  # person not allowed to see this complaint

    if request.method == "POST":  # message posted
        if 'delete' in request.POST:
            comment_id = request.POST.get('comment_id', None)
            if comment_id:
                comment = get_object_or_404(ComplaintComment, id=comment_id)
                if comment.person == request.person or request.is_education_committee:
                    comment.delete()
                    return redirect(obj)
        if 'edit' in request.POST:
            comment_id = request.POST.get('comment_id', None)
            if comment_id:
                comment = get_object_or_404(ComplaintComment, id=comment_id)
                if comment.person == request.person:
                    comment_form = ComplaintCommentForm(request.POST)
                    if comment_form.is_valid():
                        comment.delete()  # prevent duplicate comments
                        comment = comment_form.save(commit=False)
                        comment.person = request.person
                        comment.complaint = obj
                        if not reporter and not request.is_education_committee:
                            comment.public = False
                        if not request.is_education_committee:
                            comment.official = False
                        comment.save()
                        comment_form = ComplaintCommentForm()
                        return redirect(obj)

        elif 'support' in request.POST or 'nosupport' in request.POST:
            if request.person in obj.people.all() and 'nosupport' in request.POST:
                obj.people.remove(request.person)
            elif 'support' in request.POST:
                obj.people.add(request.person)
            obj.save()
            return redirect(obj)
        elif 'complete' in request.POST and request.is_education_committee:
            obj.completed = True
            obj.save()
            send_complaint_closed_notification(obj.summary, obj.reporter, request.get_full_path())
            return redirect(obj)
        elif 'reopen' in request.POST:
            obj.completed = False
            obj.save()
            return redirect(obj)
        elif 'new_comment' in request.POST:
            comment_form = ComplaintCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.person = request.person
                comment.complaint = obj
                if not reporter and not request.is_education_committee:
                    comment.public = False
                if not request.is_education_committee:
                    comment.official = False
                comment.save()
                comment_form = ComplaintCommentForm()
                send_complaint_comment_notification(obj, comment.comment, comment.person, request.get_full_path())
                return redirect(obj)
        else:
            comment_form = ComplaintCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.person = request.person
                comment.complaint = obj
                if not reporter and not request.is_education_committee:
                    comment.public = False
                if not request.is_education_committee:
                    comment.official = False
                comment.save()
                comment_form = ComplaintCommentForm()
                send_new_complaint_notification(obj, comment.comment, comment.person, request.get_full_path())
                return redirect(obj)

    if request.is_education_committee or reporter:
        complaint_comment_filter = Q()
    else:
        complaint_comment_filter = Q(public=True) | Q(person=request.person)

    complaint_comments = obj.complaintcomment_set.filter(complaint_comment_filter).extra(order_by=['published'])

    return render(request, "complaint.html", locals())


@require_lid
def complaint_new(request):
    form = ComplaintForm(initial=request.GET)

    if request.method == "POST":
        complaint_default = Complaint(reporter=Person.objects.all()[0])
        form = ComplaintForm(request.POST, instance=complaint_default)
        if form.is_valid():
            complaint_obj = form.save(commit=False)
            complaint_obj.reporter = request.person

            complaint_obj.save()

            send_new_complaint_notification(complaint_obj, complaint_obj.comment,
                                            request.person, complaint_obj.get_absolute_url())
            return redirect(complaint_obj.get_absolute_url())

    is_new = True

    return render(request, "complaint_new.html", locals())


@require_education
def complaint_edit(request, pk):
    complaint_obj = get_object_or_404(Complaint, pk=pk)

    form = ComplaintForm(instance=complaint_obj)

    if request.method == 'POST':
        form = ComplaintForm(request.POST, instance=complaint_obj)

        if form.is_valid():
            form.save(commit=True)
            return redirect(complaint_obj.get_absolute_url())

    is_new = False

    return render(request, 'complaint_new.html', locals())


class ModuleView(RequireMemberMixin, TemplateView):
    template_name = "module.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['obj'] = get_object_or_404(Module, course_code=kwargs['course_code'])
        complaints = list(context['obj'].complaint_set.all())
        for course in context['obj'].courses.all():
            complaints.extend(course.complaint_set.all())
        context['complaints'] = sorted(complaints, key=lambda x: x.id)

        return context


@require_lid
def course(request, course_code, slug):
    obj = get_object_or_404(Course, course_code=course_code)

    return render(request, "course.html", locals())


@require_lid
def course_new(request):
    form = CourseForm(initial=request.GET)
    next = request.GET.get("next", None)

    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course_obj = form.save()
            course_obj.save()
            if next and url_has_allowed_host_and_scheme(next, [request.get_host()]):
                return redirect(next)
            return redirect("education:complaint_new")

    return render(request, "course_new.html", locals())


@require_lid
def module_new(request):
    form = ModuleForm(initial=request.GET)
    next = request.GET.get("next", None)

    if request.method == "POST":
        form = ModuleForm(request.POST)
        if form.is_valid():
            module_obj = form.save()
            module_obj.save()
            if next and url_has_allowed_host_and_scheme(next, [request.get_host()]):
                return redirect(next)
            return redirect("education:complaint_new")

    return render(request, "module_new.html", locals())


def event(request, event_id):
    obj = get_object_or_404(EducationEvent, id=event_id)
    is_education = hasattr(request, 'is_education_committee') and request.is_education_committee

    return render(request, "education_event.html", locals())


@require_education
def event_new(request):
    is_new = True

    if request.method == "POST":
        form = EducationEventForm(data=request.POST)

        if form.is_valid():
            event_obj = form.save(commit=False)
            event_obj.organizer = Committee.objects.get(name="Bestuur")
            event_obj.save()
            return redirect(event_obj.get_absolute_url())
    else:
        form = EducationEventForm()

    return render(request, "education_event_form.html", locals())


@require_education
def event_edit(request, event_id):
    obj = get_object_or_404(EducationEvent, id=event_id)

    if request.method == "POST":
        form = EducationEventForm(instance=obj, data=request.POST)

        if form.is_valid():
            event_obj = form.save()
            return redirect(event_obj.get_absolute_url())
    else:
        form = EducationEventForm(instance=obj)

    return render(request, "education_event_form.html", locals())


@require_education
def event_delete(request, event_id):
    obj = get_object_or_404(EducationEvent, id=event_id)

    if request.method == "POST":
        if 'yes' in request.POST:
            obj.delete()
            return redirect('education:event_overview')
        else:
            return redirect(obj.get_absolute_url())

    return render(request, "education_event_delete.html", locals())


def event_overview(request):
    now = timezone.now()

    if request.april_active:
        new_events = EducationEvent.objects.filter_public(request).order_by("?")[:random.randint(2, 5)]
        old_events = EducationEvent.objects.filter_public(request).order_by("?")[:10]
    else:
        new_events = EducationEvent.objects.filter_public(request).filter(end__gte=now)
        old_events = EducationEvent.objects.filter_public(request).filter(begin__lte=now).order_by("-begin")[:10]

    return render(request, "education_event_overview.html", locals())


def send_new_complaint_notification(complaint_obj, comment, reporter, url):
    """
    Send notification for new complaint.
    :type complaint_obj: Complaint
    :type comment: unicode
    :type reporter: Person
    :type url: unicode
    """
    task = MailTask(template_name='education/new_complaint_notification.mail',
                    report_to=settings.EMAIL_REPORT_TO,
                    report_always=False)

    complaint_subject = complaint_obj.course if complaint_obj.course else complaint_obj.subject
    context = {'complaint_course': force_str(complaint_obj.course) if complaint_obj.course else None,
               'complaint_summary': complaint_obj.summary,
               'complaint_subject': force_str(complaint_subject),
               'complaint_comment': comment,
               'complaint_reporter': reporter.incomplete_name(),
               'url': url}

    task.add_recipient(Recipient(tos=[settings.EDUCATION_COMMITTEE_EMAIL],
                                 context=context,
                                 language='en',
                                 headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))

    task.send()


def send_complaint_comment_notification(complaint_obj, comment, reporter, url):
    """
    Send notification for new complaint comment.
    :type complaint_obj: Complaint
    :type comment: unicode
    :type reporter: Person
    :type url: unicode
    """
    task = MailTask(template_name='education/complaint_comment.mail',
                    report_to=settings.EMAIL_REPORT_TO,
                    report_always=False)

    complaint_subject = complaint_obj.course if complaint_obj.course else complaint_obj.subject
    context = {'complaint_course': force_str(complaint_obj.course) if complaint_obj.course else None,
               'complaint_summary': complaint_obj.summary,
               'complaint_subject': force_str(complaint_subject),
               'complaint_comment': comment,
               'complaint_reporter': reporter.incomplete_name(),
               'url': url}

    task.add_recipient(Recipient(tos=[settings.EDUCATION_COMMITTEE_EMAIL],
                                 context=context,
                                 language='en',
                                 headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))

    task.send()


def send_complaint_closed_notification(complaint_summary, complainant, url):
    """
    Send notification to complainant and Educational Committee that the complaint has been closed.
    :type complaint_summary: str
    :type url: unicode
    :type complainant: Person
    """
    # Send notification to complainant
    task = MailTask(template_name='education/complaint_closed.mail',
                    report_to=settings.EMAIL_REPORT_TO,
                    report_always=False)

    context = {'complaint_subject': complaint_summary,
               'complaint_complainant': complainant.incomplete_name(),
               'OC': False,
               'url': url}

    task.add_recipient(Recipient(tos=[complainant.email_address],
                                 context=context,
                                 headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))
    task.send()

    # Send notification to Educational Committee
    task_oc = MailTask(
        template_name='education/complaint_closed.mail',
        report_to=settings.EMAIL_REPORT_TO,
        report_always=False,
    )

    context_oc = {'complaint_subject': complaint_summary,
                  'OC': True,
                  'url': url}

    task_oc.add_recipient(
        Recipient(
            tos=[settings.EDUCATION_COMMITTEE_EMAIL],
            context=context_oc,
            language='en',
            headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL},
        )
    )
    task_oc.send()

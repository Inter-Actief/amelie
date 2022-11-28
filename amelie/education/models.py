# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db import transaction
from django.db.models import Max, Min
from django.db.models.signals import post_save
from django.template.defaultfilters import slugify
from django.utils.encoding import force_str
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from amelie.iamailer.mailtask import MailTask
from amelie.calendar.models import Event
from amelie.members.models import Person
from amelie.education.managers import ComplaintCommentManager, EducationEventManager
from amelie.tools.discord import send_discord
from amelie.tools.mail import PersonRecipient


class Category(models.Model):
    name_nl = models.SlugField(max_length=100, verbose_name=_('Name'))
    name_en = models.SlugField(max_length=100, verbose_name=_('Name (en)'), blank=True)

    class Meta:
        ordering = ['name_nl']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return '%s' % self.name

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl


class Page(models.Model):
    name_nl = models.CharField(max_length=100, verbose_name=_('Name'))
    name_en = models.CharField(max_length=100, verbose_name=_('Name (en)'), blank=True)
    slug = models.SlugField(max_length=100, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    content_nl = models.TextField(verbose_name=_('Content'))
    content_en = models.TextField(verbose_name=_('Content (en)'), blank=True)
    last_changed = models.DateTimeField(auto_now=True)
    position = models.IntegerField(unique=True)

    class Meta:
        ordering = ['position']
        verbose_name = _('Page')
        verbose_name_plural = _("Pages")

    def __str__(self):
        return '%s' % self.name

    def first_page(self):
        return Page.objects.order_by("position").first()

    def last_page(self):
        return Page.objects.order_by("-position").first()

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    @property
    def content(self):
        language = get_language()

        if language == "en" and self.content_en:
            return self.content_en
        else:
            return self.content_nl

    @transaction.atomic
    def swap(self, other):
        self_old, other_old = self.position, other.position

        self.position = -1
        self.save()

        other.position = self_old
        other.save()

        self.position = other_old
        self.save()

    def move_up(self):
        before = Page.objects.filter(position__lt=self.position)

        if before:
            other = Page.objects.get(position=before.aggregate(Max('position'))['position__max'])
            self.swap(other)

    def move_down(self):
        after = Page.objects.filter(position__gt=self.position)

        if after:
            other = Page.objects.get(position=after.aggregate(Min('position'))['position__min'])
            self.swap(other)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)

        if self.position is None:
            self.position = self.last_page().position + 1

        super(Page, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return '{}#{}'.format(reverse('education:overview'), self.slug)


class Period(models.Model):
    """
    Quartiles, semesters, trimesters...
    """
    year = models.PositiveIntegerField(verbose_name=_('Year'))
    name = models.CharField(max_length=5, verbose_name=_('Name'))
    start = models.DateField(verbose_name=_('Starts'))
    end = models.DateField(verbose_name=_('Ends'))

    end_lectures = models.DateField(verbose_name=_('End of lectures'))
    exam_enrollment_start = models.DateField(verbose_name=_('Exam enrollment starts'), null=True,
                                                   blank=True)
    exam_enrollment_end = models.DateField(verbose_name=_('Exam enrollment stops'), null=True,
                                                  blank=True)
    course_enrollment_start = models.DateField(verbose_name=_('Enrollment for courses starts'), null=True, blank=True)
    course_enrollment_end = models.DateField(verbose_name=_('Enrollment for courses stops'), null=True, blank=True)
    books_ordering_start = models.DateField(verbose_name=_('Book order period starts'), null=True, blank=True)
    books_ordering_end = models.DateField(verbose_name=_('Book order stops'), null=True, blank=True)

    class Meta:
        ordering = ['year', 'start', '-name']
        verbose_name = _('Part of year')
        verbose_name_plural = _('Parts of year')

    def __str__(self):
        return '%s (%s/%s)' % (self.name, self.year, self.year+1)

    def clean(self):
        super(Period, self).clean()

        if self.start is not None and self.end is not None:
            if self.start >= self.end:
                raise ValidationError(_('Start may not be after of simultaneous to end.'))

        if self.exam_enrollment_start is not None and self.exam_enrollment_end is not None:
            if self.exam_enrollment_start >= self.exam_enrollment_end:
                raise ValidationError(
                    _('Start of enrollment term for the exams may not be after or simultaneous to the end of this term.'))

        if self.course_enrollment_start is not None and self.course_enrollment_end is not None:
            if self.course_enrollment_start >= self.course_enrollment_end:
                raise ValidationError(
                    _('Start of enrollment term for courses may not be after or simultaneous to the end of this term.'))

        if self.books_ordering_start is not None and self.books_ordering_end is not None:
            if self.books_ordering_start >= self.books_ordering_end:
                raise ValidationError(
                    _('Start of the term for ordering books may not be after or simultaneous to the end of this term.'))


class BaseCourseModule(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    course_code = models.PositiveIntegerField(unique=True, verbose_name=_("Course code"),
                                              validators=[MinValueValidator(100000), MaxValueValidator(999999999)])

    def __str__(self):
        return u'%s (%s)' % (self.name, self.course_code)

    def get_absolute_url(self):
        if hasattr(self, 'course'):
            return self.course.get_absolute_url()
        elif hasattr(self, 'module'):
            return self.module.get_absolute_url()
        else:
            raise RuntimeError("Unknown subclass of BaseCourseModule")


class Module(BaseCourseModule):
    """
    A module as specified by TEM/TOM.
    """

    def get_absolute_url(self):
        return reverse('education:module', args=(), kwargs={
            'course_code': self.course_code,
            'slug': slugify(self.name),
        })

    class Meta:
        ordering = ['name', 'course_code']
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')


class Course(BaseCourseModule):
    """
    A course with a specific content
    """
    module_ptr = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="courses", null=True,
                                   verbose_name=_("Module"), blank=True)

    class Meta:
        ordering = ['name', 'course_code']
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')

    def get_absolute_url(self):
        return reverse('education:course', args=(), kwargs={
            'course_code': self.course_code,
            'slug': slugify(self.name),
        })


class Complaint(models.Model):
    """
    General education complaint
    """
    class ComplaintChoices(models.TextChoices):
        GRADING = 'Grading', _('Marking period expired')
        FACILITIES = 'Facilities', _('Facilities')
        INFORMATION = 'Information', _('Information supply')
        INTERNATIONALIZATION = 'Internationalization', _('Internationalization')
        OTHER = 'Other', _('Otherwise')

    class PeriodChoices(models.TextChoices):
        Q1 = 'Q1', _('Quarter 1')
        Q2 = 'Q2', _('Quarter 2')
        Q3 = 'Q3', _('Quarter 3')
        Q4 = 'Q4', _('Quarter 4')
        S1 = 'S1', _('Semester 1')
        S2 = 'S2', _('Semester 2')

    published = models.DateTimeField(auto_now_add=True)

    subject = models.CharField(max_length=50, choices=ComplaintChoices.choices, verbose_name=_('Subject'))
    summary = models.CharField(max_length=100, blank=True, verbose_name=_('Summary'))
    comment = models.TextField(verbose_name=_('Remarks'), blank=True)

    reporter = models.ForeignKey(Person, editable=False, verbose_name=_('Reporter'), on_delete=models.PROTECT)
    people = models.ManyToManyField(Person, verbose_name=_('People'), editable=False, related_name='personen')
    public = models.BooleanField(default=False, verbose_name=_('Public'))
    progress = models.BooleanField(default=False, verbose_name=_('Feedback on progress'))
    anonymous = models.BooleanField(default=False, verbose_name=_('Handle anonymously'))
    completed = models.BooleanField(default=False, verbose_name=_('Handled'))

    course = models.ForeignKey(BaseCourseModule, null=True, blank=True, verbose_name=_('Course or module'), on_delete=models.SET_NULL)
    part = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('Subject'))
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Year'))
    period = models.CharField(max_length=2, choices=PeriodChoices.choices, null=True, blank=True, verbose_name=_('Term'))

    class Meta:
        ordering = ['-published']
        verbose_name = _('Complaint')
        verbose_name_plural = _('Complaints')

    def __str__(self):
        return '%s (%s)' % (self.course, self.subject)

    def get_absolute_url(self):
        return reverse('education:complaint', args=(), kwargs={'complaint_id': self.id, })


class ComplaintComment(models.Model):
    """
    Comment on a complaint, e.g. progress.
    """

    published = models.DateTimeField(editable=False, auto_now_add=True)
    public = models.BooleanField(verbose_name=_('Public'), default=True)
    complaint = models.ForeignKey(Complaint, editable=False, verbose_name=_('Complaint'), on_delete=models.CASCADE)

    person = models.ForeignKey(Person, editable=False, verbose_name=_('Person'), on_delete=models.PROTECT)
    comment = models.TextField(verbose_name=_('Remarks'))

    objects = ComplaintCommentManager()

    class Meta:
        ordering = ['complaint', '-published']
        verbose_name = _('Comment on a complaint')
        verbose_name_plural = _('Comments on a complaint')


class Competition(models.Model):
    """
    This is a competition, e.g. educational bouquet.
    """

    title = models.CharField(max_length=100)

    class Meta:
        verbose_name = _('Game')
        verbose_name_plural = _('Games')

    def __str__(self):
        return '%s' % self.title


class Vote(models.Model):
    """
    This is a vote. It belongs to a competition.
    """

    person = models.ForeignKey(Person, editable=False, on_delete=models.PROTECT)
    competition = models.ForeignKey(Competition, editable=False, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _('Vote')
        verbose_name_plural = _('Votes')


class EducationEvent(Event):
    objects = EducationEventManager()

    education_organizer = models.CharField(verbose_name="organiser", max_length=100, blank=True)

    @property
    def activity_type(self):
        return "educational"

    def get_absolute_url(self):
        return reverse('education:event', args=(), kwargs={'event_id': self.id})


def progress_feedback(sender, **kwargs):
    complaint_comment = kwargs.pop('instance', None)
    complaint = complaint_comment.complaint

    if complaint.progress:
        if complaint_comment.person != complaint.reporter:  # Progress notice from reporter to reporter is not required.
            task = MailTask(from_=settings.EDUCATION_COMMITTEE_EMAIL,
                            template_name='education/complaint_progress.mail',
                            report_to=settings.EDUCATION_COMMITTEE_EMAIL,
                            report_always=False)

            complaint_subject = complaint.course if complaint.course else complaint.subject
            context = {'complaint_subject': force_str(complaint_subject),
                       'complaint_comment': complaint_comment,
                       'complaint_comment_person': complaint_comment.person.incomplete_name(),
                       'url': complaint.get_absolute_url(),
                       }

            task.add_recipient(PersonRecipient(recipient=complaint.reporter, context=context))
            task.send(delay=False)


post_save.connect(progress_feedback, sender=ComplaintComment)
post_save.connect(send_discord, sender=EducationEvent)

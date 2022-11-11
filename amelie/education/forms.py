# -*- coding: utf-8 -*-
from django import forms
from django.conf import settings
from django.forms import widgets
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from amelie.iamailer.mailtask import MailTask, Recipient
from amelie.style.forms import inject_style
from amelie.calendar.forms import EventForm
from amelie.education.models import Complaint, ComplaintComment, Page, Vote, Course, Competition, Category, EducationEvent
from amelie.tools.logic import current_academic_year_strict
from amelie.tools.widgets import DateTimeSelector


class PageForm(forms.ModelForm):
    # content = forms.CharField(label=_('Inhoud'), widget=TextEditor)

    class Meta:
        model = Page
        fields = ['name_nl', 'name_en', 'category', 'content_nl', 'content_en']


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name_nl', 'name_en']


class ComplaintCommentForm(forms.ModelForm):
    comment = forms.CharField(widget=widgets.Textarea(attrs={'rows': 5, }))
    official = forms.BooleanField(initial=True, required=False)

    class Meta:
        model = ComplaintComment
        fields = ['comment', 'public', 'official']


def calc_choices():
    result = ((None, '—'),)

    for course_type, course_type_name in Course.CourseTypes.choices:
        result = result + ((course_type_name, [(course.id, course.name) for course in
                                               Course.objects.filter(course_type=course_type)]),)

    return result


class ComplaintForm(forms.ModelForm):
    subject = forms.ChoiceField(choices=Complaint.ComplaintChoices.choices, widget=widgets.RadioSelect)
    course = forms.ChoiceField(required=False, label=_('Course'))
    part = forms.CharField(max_length=255, required=False, label=_('Subject'),
                                widget=forms.TextInput(attrs={'placeholder': _('Subject')}))
    year = forms.IntegerField(min_value=1, required=False, initial=current_academic_year_strict, label=_('Year'))

    def __init__(self, *args, **kwargs):
        super(ComplaintForm, self).__init__(*args, **kwargs)
        self.fields['course'].choices = calc_choices()

    class Meta:
        model = Complaint
        fields = ['subject', 'course', 'summary', 'comment', "public", 'progress', 'anonymous', 'part', 'year',
                  'period']

    def clean_course(self):
        cleaned_data = self.cleaned_data
        subject = cleaned_data.get('subject', None)
        course = cleaned_data.get('course', None)
        if subject == 'Grading' and not course:
            raise forms.ValidationError(_('If the deadline for revision of your exam has passed, you can select a course'))
        return Course.objects.get(id=course) if course else None

    def clean_comment(self):
        cleaned_data = self.cleaned_data
        subject = cleaned_data.get('subject', None)
        summary = cleaned_data.get('summary', '')
        comment = cleaned_data.get('comment', '')
        if subject != 'Grading' and (len(summary) == 0 or len(comment) == 0):
            raise forms.ValidationError(_('Fill in a summary and comments'))
        return cleaned_data['comment']


class EducationalBouquetForm(forms.Form):
    teacher = forms.CharField(max_length=60, label=_('Teacher'))
    course = forms.ModelChoiceField(queryset=Course.objects.all().order_by('name'), empty_label=None, label=_('Course'))
    reason = forms.CharField(max_length=300, widget=forms.Textarea, label=_('Reason'))
    author = forms.CharField(max_length=40, label=_('Author'))
    email = forms.EmailField(max_length=50, label=_('E-mail'))

    def save(self, *args, **kwargs):
        context = {'teacher': self.cleaned_data['teacher'],
                   'course': self.cleaned_data['course'],
                   'reason': self.cleaned_data['reason'],
                   'author': self.cleaned_data['author'],
                   'email': self.cleaned_data['email'],
                   }

        task = MailTask(template_name='education/educational_bouquet.mail', report_to=settings.EMAIL_REPORT_TO,
                        report_always=False)

        task.add_recipient(Recipient(tos=[settings.EDUCATION_COMMITTEE_EMAIL],
                                     context=context,
                                     headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))

        task.send()


class DEANominationForm(forms.Form):
    teacher = forms.CharField(max_length=60)
    reason = forms.CharField(max_length=300, widget=forms.Textarea)
    author = forms.CharField(max_length=40)
    email = forms.EmailField(max_length=50)

    def save(self, *args, **kwargs):
        context = {'teacher': self.cleaned_data['teacher'],
                   'reason': self.cleaned_data['reason'],
                   'author': self.cleaned_data['author'],
                   'email': self.cleaned_data['email'],
                   }

        task = MailTask(template_name='education/dea_nomination.mail', report_to=settings.EMAIL_REPORT_TO,
                        report_always=False)

        task.add_recipient(Recipient(tos=[settings.EDUCATION_COMMITTEE_EMAIL],
                                     context=context,
                                     headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))

        task.send()


class DEAVoteForm(forms.Form):
    TEACHERS = (('sikkel', 'Klaas Sikkel'), ('langerak', 'Rom Langerak'), ('keulen', 'Maurice van Keulen'))
    teacher = forms.ChoiceField(choices=TEACHERS, widget=forms.RadioSelect, required=True)
    competition = forms.ModelChoiceField(Competition.objects.all(), required=False)
    lecture = forms.MultipleChoiceField(choices=TEACHERS, widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, person, *args, **kwargs):
        super(DEAVoteForm, self).__init__(*args, **kwargs)
        self.person = person

    def clean(self):
        cleaned_data = super(DEAVoteForm, self).clean()
        vote = None
        self.competition = Competition.objects.get(title="Onderwijsprijs 2015")
        try:
            vote = Vote.objects.get(person=self.person, competition=self.competition)
        except Vote.DoesNotExist:
            pass
        if not vote:
            return cleaned_data
        else:
            raise forms.ValidationError(_('You\'ve already voted!'))

    def save(self, *args, **kwargs):
        self.competition = Competition.objects.get(title="Onderwijsprijs 2015")
        vote, created = Vote.objects.get_or_create(person=self.person, competition=self.competition)
        if not created:  # you already voted
            return

        context = {'teacher': self.cleaned_data['teacher'],
                   'person': self.person.full_name(),
                   'student_number': self.person.student.student_number() if self.person.is_student() else None,
                   'lecture': ', '.join(self.cleaned_data['lecture']),
                   'competition': force_str(self.competition),
                   }

        task = MailTask(template_name='education/dea_vote.mail', report_to=settings.EMAIL_REPORT_TO,
                        report_always=False)

        task.add_recipient(Recipient(tos=[settings.EDUCATION_COMMITTEE_EMAIL],
                                     context=context,
                                     headers={'Reply-To': settings.EDUCATION_COMMITTEE_EMAIL}))

        task.send()


class CourseForm(forms.ModelForm):
    name = forms.CharField(max_length=200, label=_("Course name"))
    course_type = forms.ChoiceField(choices=Course.CourseTypes.choices)
    course_code = forms.IntegerField(min_value=0, max_value=2147483647)

    class Meta:
        model = Course
        fields = ["name", 'course_type', 'course_code']

    def __init__(self, *args, **kwargs):
        super(CourseForm, self).__init__(*args, **kwargs)


class SearchSummariesForm(forms.Form):
    filter = forms.CharField(label=_('Name of course'), required=False)


class EducationEventForm(EventForm):
    class Meta:
        model = EducationEvent
        widgets = {
            'begin': DateTimeSelector,
            'end': DateTimeSelector,
        }
        field_classes = {
            'begin': forms.SplitDateTimeField,
            'end': forms.SplitDateTimeField
        }
        fields = ['summary_nl', 'summary_en', 'location', 'begin', 'end', "public", 'description_nl',
                  'description_en', "education_organizer"]

inject_style(SearchSummariesForm, EducationalBouquetForm)

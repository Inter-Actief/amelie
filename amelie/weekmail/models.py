from django.urls import reverse
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _l

from amelie.calendar.models import Event
from amelie.news.models import NewsItem
from amelie.members.models import Person


class WeekMailNewsArticle(models.Model):
    """
    Defines an extra news article that is added to this week mail.
    """
    title_nl = models.CharField(max_length=150)
    """
    The title of the added article
    """
    title_en = models.CharField(max_length=150)

    content_nl = models.TextField()
    """
    The body of this added article.
    """
    content_en = models.TextField()

    @property
    def title(self):
        language = get_language()

        if language == "en" and self.title_en:
            return self.title_en
        else:
            return self.title_nl

    @property
    def content(self):
        language = get_language()

        if language == "en" and self.content_en:
            return self.content_en
        else:
            return self.content_nl

    def __str__(self):
        return self.title


class WeekMail(models.Model):
    """
    Class representing a complete week mail.
    A complete week mail can be generated from this class.
    """
    class StatusOptions(models.TextChoices):
        UNSENT = 'N', _l('Not yet sent'),  # Not yet sent
        SENDING = 'U', _l('Currently sending'),  # Outgoing
        SENT = 'V', _l('Sent'),  # Sent
        ERROR = 'E', _l('Error during sending')  # Error

    class MailTypes(models.TextChoices):
        WEEKMAIL = 'W', _l("Weekly mail")
        MASTERMAIL = 'M', _l("Mastermail")
        EDUCATION_MAIL = 'E', _l("Educational mail")

    published = models.BooleanField(default=False)
    """
    This week mail is published
    """

    status = models.CharField(max_length=1, choices=StatusOptions.choices, default=StatusOptions.UNSENT)
    """
    What the current sending status is of this week mail
    """

    creation_date = models.DateTimeField(auto_now=True)
    """
    The date this week mail was created
    """

    """
    The list of activities in this week mail
    """
    new_activities = models.ManyToManyField(Event, verbose_name=_l("new events"), related_name="new_activities", blank=True)

    news_articles = models.ManyToManyField(NewsItem, verbose_name=_l("news articles"), blank=True)
    """
    The list of news articles in this week mail
    """

    added_news_articles = models.ManyToManyField(WeekMailNewsArticle, blank=True)
    """
    The list of extra added news articles in this week mail
    """

    writer = models.ForeignKey(Person, null=True, on_delete=models.SET_NULL)
    """
    The writer of this week mail
    """

    mailtype = models.CharField(verbose_name=_l("Type of mailing"), max_length=1, choices=MailTypes.choices,
                                default=MailTypes.WEEKMAIL)
    """
    Type of this mailing, normal week mail or master mail
    """

    def __str__(self):
        mailtypes_dict = {k: v for k, v in WeekMail.MailTypes.choices}
        return '%s %s-%s' % (
            mailtypes_dict[self.mailtype],
            self.creation_date.year,
            self.creation_date.isocalendar()[1] if self.mailtype == WeekMail.MailTypes.WEEKMAIL else self.creation_date.strftime('%B')
        )

    def get_absolute_url(self):
        return reverse('weekmail:preview', args=[self.pk])

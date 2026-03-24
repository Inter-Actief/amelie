from django.urls import reverse
from django.db import models
from django.db.models.signals import post_save
from django.template.defaultfilters import slugify
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _l

from amelie.activities.models import Activity
from amelie.files.models import Attachment
from amelie.members.models import Committee, Person
from amelie.tools.ariana import send_irc
from amelie.tools.discord import send_discord


class NewsItem(models.Model):
    publication_date = models.DateTimeField(auto_now_add=True)

    title_nl = models.CharField(max_length=150)
    title_en = models.CharField(max_length=175, blank=True, null=True)

    slug = models.SlugField(max_length=175, editable=False)

    introduction_nl = models.CharField(max_length=175)
    introduction_en = models.CharField(max_length=175, blank=True, null=True)

    content_nl = models.TextField()
    content_en = models.TextField(blank=True)

    publisher = models.ForeignKey(Committee, on_delete=models.PROTECT)
    author = models.ForeignKey(Person, null=True, on_delete=models.SET_NULL)

    attachments = models.ManyToManyField(Attachment, blank=True)
    activities = models.ManyToManyField(Activity, blank=True)

    pinned = models.BooleanField(default=False, help_text=_l('Choose this option to pin the news item'))

    class Meta:
        ordering = ['-publication_date']
        verbose_name = _l('News message')
        verbose_name_plural = _l('News messages')

    def __str__(self):
        return '%s' % self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(NewsItem, self).save(*args, **kwargs)

    @property
    def title(self):
        language = get_language()

        if language == "en" and self.title_en:
            return self.title_en
        else:
            return self.title_nl

    @property
    def introduction(self):
        language = get_language()

        if language == "en" and self.introduction_en:
            return self.introduction_en
        else:
            return self.introduction_nl

    @property
    def content(self):
        language = get_language()

        if language == "en" and self.content_en:
            return self.content_en
        else:
            return self.content_nl

    @property
    def is_education_item(self):
        return self.publisher.pk == Committee.education_committee().pk

    def can_edit(self, person):
        return person.is_board() or (self.publisher in person.current_committees()) or person.user.is_superuser

    def can_delete(self, person):
        return person.is_board() or person.user.is_superuser

    def get_absolute_url(self):
        return reverse('news:news-item', args=(),
                       kwargs={'id': self.id, 'year': self.publication_date.year, 'month': self.publication_date.month,
                               'day': self.publication_date.day, 'slug': self.slug, })


# IRC notifications disabled because the bot is broken -- albertskja 2023-03-28
# post_save.connect(send_irc, sender=NewsItem)
post_save.connect(send_discord, sender=NewsItem)

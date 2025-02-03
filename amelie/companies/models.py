from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db import models
from django.db.models.signals import post_save
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.translation import gettext_lazy as _l, get_language

from amelie.companies.managers import CompanyManager
from amelie.calendar.managers import EventManager
from amelie.calendar.models import Event
from amelie.activities.models import ActivityLabel
from amelie.tools.discord import send_discord

class Company(models.Model):
    name_nl = models.CharField(
        max_length=100,
        verbose_name=_l('name')
    )
    name_en = models.CharField(
        max_length=100,
        verbose_name=_l('name (en)'),
        blank=True)
    slug = models.SlugField(
        max_length=100,
        editable=False,
        unique=True
    )
    url = models.URLField()
    logo = models.ImageField(
        upload_to='companies/logos/',
        blank=True,
        null=True,
        width_field="logo_width",
        height_field="logo_height"
    )
    logo_width = models.PositiveIntegerField(
        null=True
    )
    logo_height = models.PositiveIntegerField(
        null=True
    )
    profile_nl = models.TextField(
        verbose_name=_l('profile')
    )
    profile_en = models.TextField(
        verbose_name=_l('profile (en)'),
        blank=True
    )
    short_description_nl = models.CharField(
        max_length=120,
        verbose_name=_l('short description'),
        blank=True,
    )
    short_description_en = models.CharField(
        max_length=120,
        verbose_name=_l('short description (en)'),
        blank=True
    )
    start_date = models.DateField(
        verbose_name=_l('from')
    )
    end_date = models.DateField(
        verbose_name=_l('until')
    )

    # For the Inter-Actief mobile application
    show_in_app = models.BooleanField(
        default=False,
        verbose_name=_l('show in app')
    )
    app_logo = models.ImageField(
        upload_to='companies/app_logos/',
        blank=True,
        null=True,
        width_field="app_logo_width",
        height_field="app_logo_height"
    )
    app_logo_height = models.PositiveIntegerField(
        null=True
    )
    app_logo_width = models.PositiveIntegerField(
        null=True
    )

    objects = CompanyManager()

    class Meta:
        ordering = ['name_nl']
        verbose_name = _l('Company')
        verbose_name_plural = _l('Companies')

    def __str__(self):
        return '%s' % self.name

    def clean(self):
        # Check if slug is unique
        slug = slugify(self.name_nl)

        conflicts = Company.objects.filter(slug=slug)
        if self.pk:
            conflicts = conflicts.exclude(pk=self.pk)

        if conflicts.exists():
            raise ValidationError({'name_nl': _l("The slug for this name already exists!")})

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name_nl)
        super(Company, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('companies:company_details', args=(), kwargs={'slug': self.slug})

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    @property
    def profile(self):
        language = get_language()

        if language == "en" and self.profile_en:
            return self.profile_en
        else:
            return self.profile_nl

    @property
    def short_description(self):
        language = get_language()

        if language == "en" and self.short_description_en:
            return self.short_description_en
        else:
            return self.short_description_nl


class BaseBanner(models.Model):
    picture = models.ImageField(upload_to='banners/')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, editable=False)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return '%s' % self.name

    def get_absolute_url(self):
        return reverse('companies:banner_edit', args=(), kwargs={'id': self.id, })

    def get_banner_src(self):
        return reverse('companies:banner_view', args=(), kwargs={'id': self.id, })


class WebsiteBanner(BaseBanner):
    url = models.URLField()
    views = models.PositiveIntegerField(editable=False, default=0)

    def save(self, **kwargs):
        self.slug = slugify(self.name)
        super(WebsiteBanner, self).save(**kwargs)

    class Meta:
        ordering = ['-end_date']
        verbose_name = _l('Website banner')
        verbose_name_plural = _l('Website banners')


class TelevisionBanner(BaseBanner):
    class Meta:
        ordering = ['-end_date']
        verbose_name = _l('Television banner')
        verbose_name_plural = _l('Television banners')


class VivatBanner(BaseBanner):
    url = models.URLField()
    views = models.PositiveIntegerField(editable=False, default=0)

    def save(self, **kwargs):
        self.slug = slugify(self.name)
        super(VivatBanner, self).save(**kwargs)

    class Meta:
        ordering = ['-end_date']
        verbose_name = _l('I/O Vivat banner')
        verbose_name_plural = _l('I/O Vivat banners')


class CompanyEvent(Event):
    objects = EventManager()
    company = models.ForeignKey('Company', blank=True, null=True, on_delete=models.SET_NULL)
    company_text = models.CharField(max_length=100, blank=True)
    company_url = models.URLField(blank=True)

    visible_from = models.DateTimeField()
    visible_till = models.DateTimeField()

    @property
    def activity_label(self):
        return ActivityLabel.objects.filter(name_en="Career").first()

    @property
    def activity_type(self):
        return "external"

    def get_calendar_url(self):
        return reverse('companies:event_ics', args=(), kwargs={'id': self.id})

    def get_absolute_url(self):
        return reverse('companies:event_details', args=(), kwargs={'id': self.id})

    def is_visible(self):
        return self.visible_from <= timezone.now() <= self.visible_till

post_save.connect(send_discord, sender=CompanyEvent)

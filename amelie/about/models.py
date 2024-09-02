from django.urls import reverse
from django.db import models
from django.template.defaultfilters import slugify
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _l


class Page(models.Model):
    name_nl = models.CharField(max_length=100, verbose_name=_l('Name'))
    name_en = models.CharField(max_length=100, verbose_name=_l('Name (en)'), blank=True)
    slug_nl = models.SlugField(max_length=100, editable=False)
    slug_en = models.SlugField(max_length=100, editable=False)
    educational = models.BooleanField(default=False, verbose_name=_l("Educational page?"))
    content_nl = models.TextField(verbose_name=_l('Content'))
    content_en = models.TextField(verbose_name=_l('Content (en)'), blank=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name_nl']
        verbose_name = _l('Page')
        verbose_name_plural = _l("Pages")

    def __str__(self):
        return self.name

    def save(self):
        self.slug_nl = slugify(self.name_nl)
        self.slug_en = slugify(self.name_en)
        super(Page, self).save()

    @property
    def name(self):
        language = get_language()

        if language == "en" and self.name_en:
            return self.name_en
        else:
            return self.name_nl

    @property
    def slug(self):
        language = get_language()

        if language == "en" and self.slug_en:
            return self.slug_en
        else:
            return self.slug_nl

    @property
    def content(self):
        language = get_language()

        if language == "en" and self.content_en:
            return self.content_en
        else:
            return self.content_nl

    def get_absolute_url(self):
        return reverse('about:page', kwargs={'pk': self.pk, 'slug': self.slug, })

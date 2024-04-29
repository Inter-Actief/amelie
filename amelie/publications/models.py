from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _l

from amelie.publications.managers import PublicationManager


class PublicationType(models.Model):
    type_name = models.CharField(
        max_length=150,
        blank=False,
        null=False,
        verbose_name=_l('type name'),
        unique=True,
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_l('description'),
    )
    default_thumbnail = models.ImageField(
        upload_to='data/uploads/%Y/%m/%d/',
        max_length=100,
        blank=False,
        null=False,
        verbose_name=_l('default thumbnail'),
        help_text=_l(
            'This thumbnail is shown when a publication of this type is uploaded without thumbnail.'
        ),
    )

    class Meta:
        ordering = ['type_name']
        verbose_name = _l('publication type')
        verbose_name_plural = _l('publication types')

    def __str__(self):
        return '%s' % self.type_name


class Publication(models.Model):

    name = models.CharField(max_length=150, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    date_published = models.DateTimeField(blank=False, null=False)
    publication_type = models.ForeignKey(PublicationType, on_delete=models.PROTECT)

    thumbnail = models.ImageField(upload_to='data/uploads/%Y/%m/%d/', blank=True, null=True)
    file = models.FileField(
        upload_to='data/uploads/%Y/%m/%d/',
        blank=False,
        null=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
    )

    is_featured = models.BooleanField(default=False, verbose_name=_l('featured'))
    public = models.BooleanField(default=True, verbose_name=_l('public'))

    objects = PublicationManager()

    class Meta:
        ordering = ['-date_published']
        verbose_name = _l('publication')
        verbose_name_plural = _l('publications')

    def __str__(self):
        return '%s' % self.name

    def get_thumbnail(self):
        if self.thumbnail:
            return self.thumbnail.url
        else:
            return self.publication_type.default_thumbnail.url

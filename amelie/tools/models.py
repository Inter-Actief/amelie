from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from amelie.members.models import Person


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['user']
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')

    def __str__(self):
        return str(self.user)


class DataExportInformation(models.Model):
    """
    Model to store information about a data export.
    The information that is stored differs per export type, but most of the time the details field contains
    the filters that were used for the query. The reason is given by the exporter.
    """

    export_type = models.CharField(max_length=100, verbose_name=_("Export type"),
                                   help_text=_("The type of export that was made."))

    details = models.CharField(max_length=512, verbose_name=_("Export details"),
                               help_text=_("Details about the export, like applied filters, the object that was "
                                           "exported, etc. Empty often means that no filters have been applied."))

    reason = models.CharField(max_length=512, verbose_name=_("Reason for export"),
                              help_text=_("The reason that the user gave for the export."))

    # Allows null values in DB to allow person deletion (null=True), but require it in forms (blank=False)
    exporter = models.ForeignKey(to=Person, verbose_name=_("Exporter"),
                                 help_text=_("The person that executed the export"),
                                 on_delete=models.SET_NULL, null=True, blank=False)

    exporter_text = models.CharField(max_length=255, verbose_name=_("Name of exporter"),
                                     help_text=_("String version of the exporter, for when their "
                                                 "Person object is removed."))

    date = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"),
                                help_text=_("The date and time of the export."))

    def save(self, *args, **kwargs):
        self.exporter_text = self.exporter.full_name()
        super(DataExportInformation, self).save(*args, **kwargs)

    @property
    def exporter_name(self):
        if self.exporter:
            return self.exporter.full_name()
        else:
            return self.exporter_text

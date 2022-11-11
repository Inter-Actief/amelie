import logging

import os
from django.db.models.signals import post_delete
from django.dispatch import receiver

from django.utils import timezone
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, gettext

from amelie.data_export.exporters.alexia import AlexiaDataExporter
from amelie.data_export.exporters.amelie import AmelieDataExporter
from amelie.data_export.exporters.amelie_files import AmelieFilesDataExporter
from amelie.data_export.exporters.gitlab import GitLabDataExporter
from amelie.data_export.exporters.homedirs import HomedirDataExporter
from amelie.members.models import Person


class DataExport(models.Model):
    """
    A data export containing the data for a single person.
    """

    download_code = models.CharField(max_length=50, verbose_name=_("Download code"), unique=True,
                                     help_text=_("Code with which you can download this export."))

    person = models.OneToOneField(to=Person, verbose_name=_("Person"), null=True, on_delete=models.SET_NULL,
                                  help_text=_("The person whose data export this is."))

    filename = models.FilePathField(path=settings.DATA_EXPORT_ROOT, verbose_name=_("Filename"), null=True, blank=True,
                                    help_text=_("The file name of the exported data."))

    request_timestamp = models.DateTimeField(verbose_name=_("Timestamp of request"), auto_now_add=True,
                                             help_text=_("The time that this data export was requested."))

    complete_timestamp = models.DateTimeField(verbose_name=_("Timestamp of completion"), null=True, blank=True,
                                              help_text=_("The time that this data export was completed."))

    download_count = models.IntegerField(verbose_name=_("Number of times downloaded"), default=0,
                                         help_text=_("How many times this export has been downloaded."))

    is_ready = models.BooleanField(verbose_name=_("Export is complete"), default=False,
                                   help_text=_("If this export is ready to be downloaded or not."))

    class Meta:
        verbose_name = _("Data export")
        verbose_name_plural = _("Data exports")

    @property
    def expires_on(self):
        if self.complete_timestamp:
            return self.complete_timestamp + timedelta(days=1)
        else:
            return self.request_timestamp + timedelta(weeks=1)

    @property
    def is_expired(self):
        return self.expires_on < timezone.now()

    def __str__(self):
        return gettext("Data export of {}").format(self.person if self.person else _("<unknown>"))

    def get_absolute_url(self):
        return reverse('data_export:export_details', kwargs={'slug': self.download_code})


class ApplicationStatus(models.Model):
    # Different choices for the status field.
    class StatusChoices(models.IntegerChoices):
        NOT_STARTED = 0, _("Not yet started")
        RUNNING = 1, _("Busy exporting data")
        SUCCESS = 2, _("Done exporting data")
        ERROR = 3, _("Error during exporting")

    # Different choices for the application to export data from.
    class ApplicationChoices(models.TextChoices):
        AMELIE = 'AmelieDataExporter', _("Data in the Inter-/Actief/ website and the members database.")
        AMELIE_FILES = 'AmelieFileDataExporter', _("Files you have uploaded to the Inter-/Actief/ website "
                                                   "(warning, may be very large).")
        ALEXIA = 'AlexiaDataExporter', _("Data from Alexia, the drink management system.")
        GITLAB = 'GitLabDataExporter', _("Data in GitLab, the version control system.")
        HOMEDIR = 'HomedirDataExporter', _("The home directory of your Inter-Actief active members account"
                                           " (warning, may be very large).")

    # Lookup dictionary for application choice string and the actual exporter class.
    APPLICATION_MODELS = {
        ApplicationChoices.AMELIE.value: AmelieDataExporter,
        ApplicationChoices.AMELIE_FILES.value: AmelieFilesDataExporter,
        ApplicationChoices.ALEXIA.value: AlexiaDataExporter,
        ApplicationChoices.GITLAB.value: GitLabDataExporter,
        ApplicationChoices.HOMEDIR.value: HomedirDataExporter,
    }

    data_export = models.ForeignKey(to=DataExport, verbose_name=_("Data export"), on_delete=models.CASCADE,
                                    related_name="exported_applications",
                                    help_text=_("Which data export this status belongs to"))

    application = models.CharField(max_length=40, choices=ApplicationChoices.choices, verbose_name=_("Application"),
                                   help_text=_("The name of the application you want to export data from."))

    status = models.IntegerField(choices=StatusChoices.choices, verbose_name=_("Export status"), default=0,
                                 help_text=_("The status of the export from this application."))

    class Meta:
        verbose_name = _("Application status")
        verbose_name_plural = _("Application statuses")

    def __str__(self):
        return gettext("Export status for {} of {} ({})").format(self.get_application_display(), self.data_export, self.get_status_display())


@receiver(post_delete, sender=DataExport)
def data_export_post_delete_hook(sender, **kwargs):
    # Delete the export file on-disk
    data_export = kwargs['instance']
    if data_export.filename and os.path.isfile(data_export.filename):
        os.remove(data_export.filename)
    else:
        logging.getLogger(__name__).error("Could not remove file {}, is not a file!".format(data_export.filename))

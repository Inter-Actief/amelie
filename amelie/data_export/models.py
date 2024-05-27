import logging

import os
from django.db.models.signals import post_delete
from django.dispatch import receiver

from django.utils import timezone
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l, gettext as _

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

    download_code = models.CharField(max_length=50, verbose_name=_l("Download code"), unique=True,
                                     help_text=_l("Code with which you can download this export."))

    person = models.OneToOneField(to=Person, verbose_name=_l("Person"), null=True, on_delete=models.SET_NULL,
                                  help_text=_l("The person whose data export this is."))

    filename = models.FilePathField(path=settings.DATA_EXPORT_ROOT, verbose_name=_l("Filename"), null=True, blank=True,
                                    help_text=_l("The file name of the exported data."))

    request_timestamp = models.DateTimeField(verbose_name=_l("Timestamp of request"), auto_now_add=True,
                                             help_text=_l("The time that this data export was requested."))

    complete_timestamp = models.DateTimeField(verbose_name=_l("Timestamp of completion"), null=True, blank=True,
                                              help_text=_l("The time that this data export was completed."))

    download_count = models.IntegerField(verbose_name=_l("Number of times downloaded"), default=0,
                                         help_text=_l("How many times this export has been downloaded."))

    is_ready = models.BooleanField(verbose_name=_l("Export is complete"), default=False,
                                   help_text=_l("If this export is ready to be downloaded or not."))

    class Meta:
        verbose_name = _l("Data export")
        verbose_name_plural = _l("Data exports")

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
        return _("Data export of {}").format(self.person if self.person else _l("<unknown>"))

    def get_absolute_url(self):
        return reverse('data_export:export_details', kwargs={'slug': self.download_code})


class ApplicationStatus(models.Model):
    # Different choices for the status field.
    class StatusChoices(models.IntegerChoices):
        NOT_STARTED = 0, _l("Not yet started")
        RUNNING = 1, _l("Busy exporting data")
        SUCCESS = 2, _l("Done exporting data")
        ERROR = 3, _l("Error during exporting")

    # Different choices for the application to export data from.
    class ApplicationChoices(models.TextChoices):
        AMELIE = 'AmelieDataExporter', _l("Data in the Inter-/Actief/ website and the members database.")
        AMELIE_FILES = 'AmelieFileDataExporter', _l("Files you have uploaded to the Inter-/Actief/ website "
                                                   "(warning, may be very large).")
        ALEXIA = 'AlexiaDataExporter', _l("Data from Alexia, the drink management system.")
        GITLAB = 'GitLabDataExporter', _l("Data in GitLab, the version control system.")
        HOMEDIR = 'HomedirDataExporter', _l("The home directory of your Inter-Actief active members account"
                                           " (warning, may be very large).")

    # Lookup dictionary for application choice string and the actual exporter class.
    APPLICATION_MODELS = {
        ApplicationChoices.AMELIE.value: AmelieDataExporter,
        ApplicationChoices.AMELIE_FILES.value: AmelieFilesDataExporter,
        ApplicationChoices.ALEXIA.value: AlexiaDataExporter,
        ApplicationChoices.GITLAB.value: GitLabDataExporter,
        ApplicationChoices.HOMEDIR.value: HomedirDataExporter,
    }

    data_export = models.ForeignKey(to=DataExport, verbose_name=_l("Data export"), on_delete=models.CASCADE,
                                    related_name="exported_applications",
                                    help_text=_l("Which data export this status belongs to"))

    application = models.CharField(max_length=40, choices=ApplicationChoices.choices, verbose_name=_l("Application"),
                                   help_text=_l("The name of the application you want to export data from."))

    status = models.IntegerField(choices=StatusChoices.choices, verbose_name=_l("Export status"), default=0,
                                 help_text=_l("The status of the export from this application."))

    class Meta:
        verbose_name = _l("Application status")
        verbose_name_plural = _l("Application statuses")

    def __str__(self):
        return _("Export status for {} of {} ({})").format(self.get_application_display(), self.data_export, self.get_status_display())


@receiver(post_delete, sender=DataExport)
def data_export_post_delete_hook(sender, **kwargs):
    # Delete the export file on-disk
    data_export = kwargs['instance']
    if data_export.filename and os.path.isfile(data_export.filename):
        os.remove(data_export.filename)
    else:
        logging.getLogger(__name__).error("Could not remove file {}, is not a file!".format(data_export.filename))

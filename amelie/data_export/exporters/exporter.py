import logging
import os
import shutil
from typing import Optional

from django.conf import settings


class DataExporter:
    default_enabled = True

    def __init__(self, data_export):
        """
        Initializes a Data Exporter for a given data export
        :param data_export: The data export that is being executed
        :type data_export: amelie.data_export.models.DataExport
        """
        self.data_export = data_export
        self.filename = os.path.join(settings.DATA_EXPORT_ROOT,
                                     "{}-{}.zip".format(data_export.download_code, self.__class__.__name__))
        self.tempdir = os.path.join(settings.DATA_EXPORT_ROOT, str(data_export.download_code))
        self.log = logging.getLogger(__name__)

        # Create temporary directory
        os.makedirs(self.tempdir)

    def export_data(self) -> Optional[str]:
        """
        Export data from this application to a .zip file specified by self.filename.
        Returns the file name if it has exported a file to that location.

        :return The file name if it has exported a file to that location or None if no file was exported.
        """
        pass

    def post_export_cleanup(self):
        """
        Make the exporter clean up after itself.
        Will be called both if the exporter completed successfully, or if it crashes/fails.
        """
        # Remove temporary directory if it exists.
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

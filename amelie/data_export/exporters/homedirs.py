import os
import time

import requests
import shutil

from django.conf import settings

from amelie.data_export.exporters.exporter import DataExporter


class DataHoarderError(Exception):
    pass


class HomedirDataExporter(DataExporter):
    default_enabled = False

    def export_data(self):
        self.log.debug("Exporting home directory for {} to {}".format(self.data_export.person, self.filename))

        # Check if user is active. If not, this exporter cannot return anything.
        ad_name = self.data_export.person.get_adname()
        if not ad_name:
            return None

        data_hoarder_url = settings.DATA_HOARDER_CONFIG['url']
        data_hoarder_key = settings.DATA_HOARDER_CONFIG['key']
        data_hoarder_basedir = settings.DATA_HOARDER_CONFIG['export_basedir']
        verify_ssl = settings.DATA_HOARDER_CONFIG['check_ssl']

        # Initiate export with the DataHoarder
        init = requests.post(url="{}/{}/".format(data_hoarder_url, ad_name), json={'accessToken': data_hoarder_key},
                             verify=verify_ssl)
        if init.status_code != 200:
            raise DataHoarderError(init.content.decode("utf-8"))

        finished = False
        data = init.json()

        # Monitor status
        while not finished:
            time.sleep(5)
            req = requests.post(url="{}/{}/".format(data_hoarder_url, ad_name), json={'accessToken': data_hoarder_key},
                                verify=verify_ssl)
            if req.status_code != 200:
                raise DataHoarderError(req.content.decode("utf-8"))
            else:
                data = req.json()

            if data['status'] == 2:
                finished = True
            elif data['status'] == 3:
                raise DataHoarderError(data['error_msg'])

        # Copy the file from the data hoarder dir to the filename required by the script and remove the source file.
        shutil.copy(os.path.join(data_hoarder_basedir, data['filename']), self.filename)
        os.remove(os.path.join(data_hoarder_basedir, data['filename']))

        return self.filename

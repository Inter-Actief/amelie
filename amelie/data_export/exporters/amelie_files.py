import json
import os
from zipfile import ZipFile

from amelie.files.models import Attachment
from amelie.data_export.exporters.exporter import DataExporter
from amelie.members.models import Photographer


class AmelieFilesDataExporter(DataExporter):
    default_enabled = False

    def export_data(self):
        self.log.debug("Exporting amelie files for {} to {}".format(self.data_export.person, self.filename))

        with ZipFile(self.filename, 'w') as export_file:

            attachments = Attachment.objects.filter(owner__person=self.data_export.person)

            attachment_data = {'files': []}
            for attachment in attachments:
                filename = os.path.basename(attachment.file.path)
                export_file.write(attachment.file.path, arcname=os.path.join("files", filename))
                attachment_data['files'].append({
                    'filename': filename,
                    'caption': str(attachment.caption),
                    'mimetype': str(attachment.mimetype),
                    'created_on': str(attachment.created),
                    'last_modified': str(attachment.modified),
                    'public': attachment.public,
                })

            export_file.writestr(
                'files.json',
                json.dumps(attachment_data, indent=2, sort_keys=True)
            )

        return self.filename

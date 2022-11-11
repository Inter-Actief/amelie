import base64
import os

import json
from zipfile import ZipFile

from amelie.data_export.exporters.exporter import DataExporter
from amelie.personal_tab.alexia import get_alexia, AlexiaCallError


class AlexiaDataExporter(DataExporter):
    def __init__(self, *args, **kwargs):
        super(AlexiaDataExporter, self).__init__(*args, **kwargs)
        self.alexia = get_alexia()
        self.student_number = None
        self.employee_number = None

    def export_data(self):
        self.log.debug("Exporting alexia data for {} to {}".format(self.data_export.person, self.filename))

        # Check if we have a good connection with Alexia
        if self.alexia is None:
            self.log.error("Alexia instance was not available when exporting!")
            return None

        # Check if the person we are exporting actually has a student or employee account (only accounts supporting Alexia).
        if hasattr(self.data_export.person, 'student'):
            self.student_number = self.data_export.person.student.student_number()
        if hasattr(self.data_export.person, 'employee'):
            self.employee_number = self.data_export.person.employee.employee_number()

        if self.student_number is None and self.employee_number is None:
            self.log.info("This person does not have a student or employee number, "
                          "so we cannot determine their Alexia account.")
            return None

        # Check which of these accounts have an alexia account, and export those accounts.
        student_exists = self.alexia.user.exists(radius_username=self.student_number)
        employee_exists = self.alexia.user.exists(radius_username=self.employee_number)

        accounts = []
        if student_exists:
            accounts.append(self.student_number)
        if employee_exists:
            accounts.append(self.employee_number)

        if not accounts:
            self.log.info("This person has no Alexia account, so we cannot export any info about them.")
            return None

        with ZipFile(self.filename, 'w') as export_file:
            for account in accounts:
                account_files = []
                account_data = {}

                # User that is linked to this account in amelie
                try:
                    account_data['user'] = self.alexia.user.get(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling user.get: {}".format(e))

                # Membership relation that this object has with our organization
                try:
                    account_data['membership'] = self.alexia.user.get_membership(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling user.get_membership: {}".format(e))

                # RfidCards that are linked to that user in alexia for our organization
                try:
                    account_data['rfids'] = self.alexia.rfid.list(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling rfid.list: {}".format(e))

                # Authorizations that are linked to that user in alexia for our organization
                try:
                    account_data['authorizations'] = self.alexia.authorization.list(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling authorization.list: {}".format(e))

                # Orders that were made
                try:
                    account_data['orders'] = self.alexia.order.list(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling order.list: {}".format(e))

                # BartenderAvailabilities that the user has entered
                try:
                    account_data['availabilities'] = self.alexia.user.get_availabilities(account)
                except AlexiaCallError as e:
                    self.log.warning("Error while calling user.get_availabilities: {}".format(e))

                # IVA certificate for this user (including file)
                try:
                    iva = self.alexia.user.get_iva_certificate(account)
                    if iva is not None:
                        export_file.writestr(
                            os.path.join(account, 'iva_certificate.pdf'),
                            base64.b64decode(iva['certificate_data'])
                        )
                except AlexiaCallError as e:
                    self.log.warning("Error while calling user.get_iva_certificate: {}".format(e))

                # Write the json file to the zip
                export_file.writestr(
                    os.path.join(account, 'alexia.json'.format()),
                    json.dumps(account_data, indent=2, sort_keys=True)
                )

                # Write the files to the zip
                for file in account_files:
                    filename = os.path.basename(file)
                    export_file.write(file, arcname=os.path.join(account, filename))

        return self.filename

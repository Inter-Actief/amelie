import asyncio
import logging

from django.conf import settings
from pyipp import IPP
from pyipp.enums import IppOperation


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


INFO_ATTRIBUTES = [
    "copies-default",
    "finishings-default",
    "media-default",
    "media-col-default",
    #"orientation-requested-default",
    "output-bin-default",
    "output-mode-default",
    "print-quality-default",
    "printer-resolution-default",
    "sides-default",
    "print-color-mode-default",
    "print-content-optimize-default",
    "print-scaling-default",
    "copies-supported",
    "finishings-supported",
    "media-supported",
    "media-col-supported",
    #"orientation-requested-supported",
    "output-bin-supported",
    "output-mode-supported",
    "print-quality-supported",
    "printer-resolution-supported",
    "sides-supported",
    "print-color-mode-supported",
    "print-content-optimize-supported",
    "print-scaling-supported",
    "generated-natural-language-supported",
    "printer-uri-supported",
    "uri-security-supported",
    "uri-authentication-supported",
    "printer-name",
    "printer-location",
    "printer-info",
    "printer-make-and-model",
    "printer-state",
    "printer-state-reasons",
    "ipp-versions-supported",
    "operations-supported",
    "multiple-document-jobs-supported",
    "multiple-operation-time-out",
    "natural-language-configured",
    "charset-configured",
    "charset-supported",
    "document-format-supported",
    "document-format-default",
    "printer-is-accepting-jobs",
    "queued-job-count",
    "pdl-override-supported",
    "printer-up-time",
    "compression-supported",
    "color-supported",
    "job-creation-attributes-supported",
    "media-bottom-margin-supported",
    "media-left-margin-supported",
    "media-right-margin-supported",
    "media-source-supported",
    "media-top-margin-supported",
    "media-type-supported",
    "media-size-supported",
    "pages-per-minute",
    "pages-per-minute-color",
    "printer-alert",
    "printer-alert-description",
    "printer-device-id",
    "printer-icons",
    "printer-more-info",
    "printer-uuid",
    "job-impressions-supported",
    "printer-geo-location",
    "printer-supply-info-uri",
    "media-ready",
    "media-col-ready",
    "identify-actions-default",
    "identify-actions-supported",
    "ipp-features-supported",
    "printer-input-tray",
    "printer-output-tray",
    "print_wfds",
    "document-format-varying-attributes",
    "multiple-operation-time-out-action",
    "printer-organization",
    "printer-organizational-unit",
    "printer-get-attributes-supported",
    "which-jobs-supported",
    "printer-current-time",
    "printer-config-change-time",
    "printer-config-change-date-time",
    "printer-state-change-time",
    "printer-state-change-date-time",
    "printer-strings-languages-supported",
    "printer-strings-uri",
    "printer-mandatory-job-attributes",
    "jpeg-k-octets-supported",
    "jpeg-x-dimension-supported",
    "jpeg-y-dimension-supported",
    "jpeg-features-supported",
    "mopria-certified",
    "pwg-raster-document-resolution-supported",
    "pwg-raster-document-sheet-back",
    "pwg-raster-document-type-supported",
    "job-password-supported",
    "job-password-length-supported",
    "job-password-encryption-supported",
    "job-password-repertoire-supported",
    "job-password-repertoire-configured",
]


class IPPPrinter:
    # References for IPP protocol:
    # - https://www.rfc-editor.org/rfc/rfc8011
    # - https://istopwg.github.io/ipp/ippguide.html#submitting-print-jobs

    def __init__(self, printer_key):
        self.printer_key = printer_key
        self.printer_info = settings.PERSONAL_TAB_PRINTERS[printer_key]
        self.ipp = None

    def connect(self):
        self.ipp = IPP(self.printer_info['ipp_url'])

    def printer_attributes(self):
        if self.ipp is None:
            self.connect()
        loop = get_event_loop()
        request_data = {
            "operation-attributes-tag": {
                "requested-attributes": INFO_ATTRIBUTES,
            },
        }
        logging.debug(request_data)
        logging.info(f"{self.printer_key} Requesting printer attributes")
        response_data = loop.run_until_complete(self.ipp.execute(
            IppOperation.GET_PRINTER_ATTRIBUTES,
            request_data,
        ))
        return response_data

    def printer_jobs(self):
        if self.ipp is None:
            self.connect()
        loop = get_event_loop()
        logging.info(f"{self.printer_key} Requesting job list")
        response_data = loop.run_until_complete(self.ipp.execute(
            IppOperation.GET_JOBS,
            {},
        ))
        jobs = response_data.get('jobs', [])
        response_jobs = []
        for job in jobs:
            job_details = self.printer_job_details(job_id=job['job-id'])
            job_details['basic'] = job
            response_jobs.append(job_details)
        return response_jobs

    def printer_job_details(self, job_id):
        if self.ipp is None:
            self.connect()
        loop = get_event_loop()
        request_data = {
            "operation-attributes-tag": {
                "job-id": job_id
            },
        }
        logging.debug(request_data)
        logging.info(f"{self.printer_key} Requesting attributes for job '{job_id}'")
        response_data = loop.run_until_complete(self.ipp.execute(
            IppOperation.GET_JOB_ATTRIBUTES,
            request_data,
        ))
        return response_data

    def create_job(self, job_name, num_copies=1, dual_sided=False, colour=False):
        """
        Example request:
        {
            VERSION 2.0
            OPERATION Create-Job

            GROUP operation-attributes-tag
            ATTR charset "attributes-charset" "utf-8"
            ATTR naturalLanguage "attributes-natural-language" "en"
            ATTR uri "printer-uri" "ipp://printer.example.com/ipp/print"
            ATTR name "requesting-user-name" "John Doe"

            GROUP Job-attributes-tag
            ATTR keyword media "na_letter_8.5x11in"

            EXPECT Job-id OF-TYPE integer
        }
        """
        if self.ipp is None:
            self.connect()
        loop = get_event_loop()
        request_data = {
            "operation-attributes-tag": {
                "requesting-user-name": "Amelie",
                "job-name": f"Amelie Print - {job_name}",
            },
            "job-attributes-tag": {
                "media": self.printer_info['settings']['media_format'],
                "multiple-document-handling": self.printer_info['settings']['multiple_document_handling'],
                "copies": num_copies,
                "sides": "two-sided-long-edge" if dual_sided else "one-sided",
                "print-color-mode": "color" if colour else "monochrome",
            }
        }
        logging.info(f"{self.printer_key} Creating new job '{job_name}' with {num_copies} copies, {dual_sided=}, {colour=}")
        logging.debug(request_data)
        response_data = loop.run_until_complete(self.ipp.execute(
            IppOperation.CREATE_JOB,
            request_data,
        ))
        logging.debug(response_data)
        return response_data

    def send_document(self, job_id, document):
        """
        Example request:
        {
            VERSION 2.0
            OPERATION Send-Document

            GROUP operation-attributes-tag
            ATTR charset "attributes-charset" "utf-8"
            ATTR naturalLanguage "attributes-natural-language" "en"
            ATTR uri "printer-uri" "ipp://printer.example.com/ipp/print"
            ATTR integer "job-id" $job-id
            ATTR name "requesting-user-name" "John Doe"
            ATTR mimeMediaType "document-format" "$filetype"
            ATTR boolean "last-document" true

            FILE $filename
        }
        """
        if self.ipp is None:
            self.connect()
        loop = get_event_loop()
        request_data = {
            "operation-attributes-tag": {
                "job-id": job_id,
                "requesting-user-name": "Amelie",
                "document-name": f"{document.name}",
                "document-format": self.printer_info['settings']['document_format'],
                "last-document": True,
            },
            "data": None
        }
        logging.debug(request_data)
        document.file.seek(0)
        request_data['data'] = document.file.read()
        logging.info(f"{self.printer_key}#{job_id} Sending document of {len(request_data['data'])} bytes to printer")
        response_data = loop.run_until_complete(self.ipp.execute(
            IppOperation.SEND_DOCUMENT,
            request_data,
        ))
        logging.debug(response_data)
        return response_data

    def print_document(self, document, job_name, num_copies=1, dual_sided=False):
        if self.ipp is None:
            self.connect()
        job_name = job_name[:250]  # Job names may not exceed 255 characters, so truncate to 250 if necessary
        create_response = self.create_job(job_name=job_name, num_copies=num_copies, dual_sided=dual_sided)
        if create_response['status-code'] != 0:
            status_msg = create_response.get('operation-attributes', {}).get('status-message', '')
            raise ValueError(f"Failed to create print job, status-code {create_response['status-code']}: {status_msg} - {create_response}")
        jobs = create_response['jobs']
        if len(jobs) < 1:
            status_msg = create_response.get('operation-attributes', {}).get('status-message', '')
            raise ValueError(f"Failed to create print job, status-code {create_response['status-code']}: {status_msg} - {create_response}")
        elif len(jobs) > 1:
            logging.warning(f"Multiple jobs returned for job name {job_name}, using first one.")
            logging.info(f"Jobs: {jobs}")
        job_id = jobs[0]['job-id']
        if self.printer_info['settings']['document_format'] != 'application/pdf':
            # TODO: If printer does not support application/pdf format, convert to the wanted format first.
            raise ValueError(f"The selected printer does not support printing PDF files.")
        return self.send_document(job_id=job_id, document=document)

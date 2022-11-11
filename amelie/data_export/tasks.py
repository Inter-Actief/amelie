import logging
import os
import shutil
import traceback
from zipfile import ZipFile

from celery import shared_task, group
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation

from amelie.data_export.models import ApplicationStatus
from amelie.iamailer import MailTask
from amelie.tools.mail import PersonRecipient


# Time limit increased to 1 hour because the data export including homedirs might take a long time.
@shared_task(time_limit=1 * 60 * 60)
def export_data(data_export):
    """
    Export the data for a given person
    :param data_export: The data export to export for.
    :type data_export: amelie.data_export.models.DataExport
    """
    # Create a celery workflow that will execute each application's export task,
    # and then executes the mail sender function

    # Execute each app's export task,
    logging.getLogger(__name__).info("Exporting data for {}".format(data_export))
    (group(execute_exporter.s(data_export, x) for x in data_export.exported_applications.all())
     # followed by the file zip callback,
     | zip_results.s(data_export)
     # followed by the mail callback
     | mail_person.s(data_export)
     )()  # And execute the workflow (the last two brackets)


@shared_task
def execute_exporter(data_export, application_status, **kwargs):
    """
    Execute an exporter for a given Person and ApplicationStatus
    :param data_export: The data export object.
    :type data_export: amelie.data_export.models.DataExport
    :param application_status: The application to run the exporter for
    :type application_status: amelie.data_export.models.ApplicationStatus
    :return: The filename that was returned by the exporter.
    """
    logging.getLogger(__name__).debug("Running exporter for {} - application {}".format(data_export.person,
                                                                                        application_status.application))

    # Get an instance of the DataExporter that we need to run
    try:
        exporter = ApplicationStatus.APPLICATION_MODELS[application_status.application](data_export)
    except Exception as e:
        traceback.print_exc()
        # Something went wrong! Set the application status to error, report the error to Sentry and quit.
        logging.getLogger(__name__).error("Could not initialize data exporter for application {} for user {}: {}".format(
            application_status.application,
            data_export.person,
            e
        ))
        #from raven.contrib.django.raven_compat.models import client
        #client.captureException()
        traceback.print_exc()
        application_status.status = ApplicationStatus.StatusChoices.ERROR
        application_status.save()
        # Remove temporary directory if it exists. (The exporter creates it during init)
        tempdir = os.path.join(settings.DATA_EXPORT_ROOT, str(data_export.download_code))
        if os.path.isdir(tempdir):
            shutil.rmtree(tempdir)
        return None

    # Update the application status to say we are running.
    application_status.status = ApplicationStatus.StatusChoices.RUNNING
    application_status.save()

    # Run the exporter and hope for the best.
    path = None
    try:
        path = exporter.export_data()
    except Exception as e:
        traceback.print_exc()
        # Something went wrong! Set the application status to error and report the error to Sentry
        logging.getLogger(__name__).error("Error while exporting data for application {} for user {}: {}".format(
            application_status.application,
            data_export.person,
            e
        ))
        #from raven.contrib.django.raven_compat.models import client
        #client.captureException()
        traceback.print_exc()
        application_status.status = ApplicationStatus.StatusChoices.ERROR
        application_status.save()

    else:
        # Everything was fine, set the application status to success
        application_status.status = ApplicationStatus.StatusChoices.SUCCESS
        application_status.save()

    # Execute exporter post-execute cleanup hook
    exporter.post_export_cleanup()

    # Finally return the file path that the exporter has generated
    return path


@shared_task
def zip_results(results, data_export):
    """
    Zip the resulting filenames together into a big zip file and add metadata about the export.
    Then, delete the original files and save the big zip's filename in the data export.
    Returns the path to the zip file.

    :param results: List of paths of the results of the exporters.
                    Paths can be None, that means there is no file or the exporter failed somewhere,
                    but that's not our fault, so just don't include those.
    :type results: list(str)
    :param data_export: The data export object
    :type data_export: amelie.data_export.models.DataExport
    :return The path to the big zip file.
    :rtype str
    """
    log = logging.getLogger(__name__)
    log.debug("Combining resulting files into one zip file.")

    # If the person only selected one export, results will be a string, if they selected more than
    # one, it will be al list. Convert the string into a 1-long list if it is a string to avoid problems.
    if type(results) == str:
        results = [results]

    # Create the export directory if it does not exist
    if not os.path.exists(settings.DATA_EXPORT_ROOT):
        os.makedirs(settings.DATA_EXPORT_ROOT)

    # Create a file for the resulting export
    combined_file_path = os.path.join(settings.DATA_EXPORT_ROOT, '{}.zip'.format(data_export.download_code))
    with ZipFile(combined_file_path, 'w') as zipfile:
        # Add all of the resulting exporter files to the .zip file
        for file in results:
            if file and os.path.isfile(file):
                try:
                    log.debug("Adding file {} to zip file {}.".format(file, combined_file_path))
                    zipfile.write(file, os.path.relpath(file, settings.DATA_EXPORT_ROOT))
                except Exception as e:
                    log.error("Could not add file {} to combined zip file: {}".format(file, e))
                    #from raven.contrib.django.raven_compat.models import client
                    #client.captureException()
                    traceback.print_exc()
            elif file:
                log.warning("Could not add file {} to archive, this is not a valid file path.".format(file))

        # Set the export completed date
        data_export.complete_timestamp = timezone.now()

        # Generate a metadata file for this export to include in the root of the .zip
        metadata_text = render_to_string('data_export/metadata/metadata.txt', {'obj': data_export})
        metadata_filename = os.path.join(settings.DATA_EXPORT_ROOT, 'metadata.txt')
        with open(metadata_filename, 'w') as metadata_file:
            metadata_file.write(metadata_text)

        # Add the metadata file to the zip
        zipfile.write(metadata_filename, os.path.relpath(metadata_filename, settings.DATA_EXPORT_ROOT))

        # Remove the metadata file.
        os.remove(metadata_filename)

    # Delete the original files
    for file in results:
        if file and os.path.isfile(file):
            log.debug("Removing original file {}".format(file))
            os.remove(file)

    # Set the filename in the data_export object
    data_export.filename = combined_file_path

    # Set the data_export as complete
    data_export.is_ready = True

    # Save the data export
    data_export.save()

    return combined_file_path


@shared_task
def mail_person(path, data_export):
    """
    Send an e-mail to the owner of this data export to tell him his data export is ready for download.
    :param data_export: The data export to send a mail for.
    :type data_export: amelie.data_export.models.DataExport
    """
    person = data_export.person
    current_language = translation.get_language()
    try:
        translation.activate(person.preferred_language)

        task = MailTask(from_='Inter-Actief Data-exporter <www@inter-actief.net>',
                        template_name='data_export/mails/export_complete.mail',
                        report_to='Inter-Actief Data-exporter <www@inter-actief.net>',
                        report_always=False)
        task.add_recipient(PersonRecipient(
            recipient=person,
            context={'data_export': data_export, 'base_url': settings.ABSOLUTE_PATH_TO_SITE},
            attachments=[],
        ))

        # Send e-mail
        task.send()
    finally:
        translation.activate(current_language)

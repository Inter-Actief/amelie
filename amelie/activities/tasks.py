import logging
from multiprocessing import context
import os

from amelie import settings
from amelie.activities.models import Activity
from amelie.iamailer.mailtask import MailTask, Recipient
from amelie.members.models import Photographer
from amelie.tools.const import TaskPriority
from amelie.tools.mail import PersonRecipient
from celery import shared_task, group, chord

from amelie.files.models import Attachment


logger = logging.getLogger(__name__)


@shared_task(name="default.save_photos")
def save_photos(folder, photos, activity, photographer, public, sendEmail):
    """
    Upload a batch of photos to the server and add them to an activity.

    This task will create and launch a Celery workflow with a new Task for each photo that needs to be uploaded.

    :param folder: The folder that contains the photos to be processed.
    :param photos: List of photo file paths that should be uploaded from the folder.
    :param activity: Which activity to add the photos to.
    :param photographer: Who is the photographer of the photos.
    :param public: If the photo is public or not.
    :param sendEmail: If an email should be sent to the members that attended this event.

    :return: Dictionary with the number of tasks scheduled:
             {
               'scheduled_tasks': The number of save tasks scheduled.
             }
    """
    logger.info(f"Starting tasks to save {len(photos)} photos for activity {activity.id}")
    # If sendEmail is True, send an email to the members that attended this event
    if(sendEmail):
        # Send email to members that attended the event
        pass # TODO: Implement email sending logic here
        send_photo_info_mail(activity_id=activity.id, photographer_id=photographer.id)


    # Build a Celery workflow that will save all the photos
    num_photos = len(photos)
    group(
        save_single_photo.s(
            folder=folder, photo=photo, activity=activity, photographer=photographer,
            public=public, progress=(i+1), total=num_photos
        ) for i, photo in enumerate(photos)
    ).delay()  # And execute the workflow (the last `.delay()`)
    logger.info(f'{num_photos} processing tasks scheduled and started.')
    return {'scheduled_tasks': num_photos}


@shared_task(name="default.send_photo_info_mail")
def send_photo_info_mail(activity_id: int, photographer_id: int):
    """
    Send an email to the members that attended the event, informing them that photos have been added to the activity.

    

    :param activity_id: The ID of the activity to which the photos have been added.
    :param photographer_id: The ID of the photographer who added the photos.

    :return: Dictionary with the number of tasks scheduled:
             {
               'scheduled_tasks': The number of save tasks scheduled.
             }
    """
    photographer = Photographer.objects.get(id=photographer_id)
    activity = Activity.objects.get(id=activity_id)
    logger.info(f"Sending an email that photos have been added to members that attended activity {activity_id}")
    logger.info("Activity internals: %s", activity.__dict__)

    # Get the email adresses of the members that attended the event
    activity_participants = activity.participants.all()

    context = {
        'activity': activity,
        'photographer': photographer,
        'plain_subject': f"Photos added to activity {activity.activity_label.name_en}"
    }

    task = MailTask(template_name='photos_uploaded.mail', report_to=settings.EMAIL_REPORT_TO,
                    report_always=False, priority=TaskPriority.MEDIUM )
    for person in activity_participants:
 
        task.add_recipient(PersonRecipient(recipient=person,
                                 context=context
                                 ))
    task.send() 


# acks_late makes it so that the task is retried if the worker crashes before it finishes.
@shared_task(name="default.save_single_photo", acks_late=True)
def save_single_photo(folder, photo, activity, photographer, public, progress=None, total=None):
    """
    Upload a single photo to the server and adds it to an activity.

    :param folder: The folder that contains the photos to be processed.
    :param photo: Path to the photo that should be uploaded from the folder.
    :param activity: Which activity to add the photos to.
    :param photographer: Who is the photographer of the photos.
    :param public: If the photo is public or not.
    :param progress: Counter to keep track of how many photos have been processed already.
    :param total: The total number of photos to be processed.

    :return: Dictionary with the number of tasks scheduled:
             {
               'scheduled_tasks': The number of save tasks scheduled.
             }
    """
    if not progress:
        progress = "??"
    if not total:
        total = "??"

    logger.info(f"[{progress}/{total}] Saving photo {photo}...")

    success = True
    exception = None
    try:
        file = os.path.join(folder, photo)
        attachment = Attachment(file=file, caption='', owner=photographer, public=public)
        attachment.save(create_thumbnails=True)
        logger.info(f"[{progress}/{total}] Adding photo to activity {activity}...")
        activity.photos.add(attachment)
        activity.save()
    except Exception as e:
        success = False
        exception = str(e)
        logger.error(f"[{progress}/{total}] Error saving photo {photo}: {e}")
    else:
        logger.info(f"[{progress}/{total}] Photo {photo} saved successfully.")
    return {
        'photo': photo,
        'progress': progress,
        'total_tasks': total,
        'success': success,
        'exception': exception,
    }

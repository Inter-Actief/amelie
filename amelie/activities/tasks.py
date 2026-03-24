import logging
import os

from celery import shared_task, group, chord

from amelie.files.models import Attachment


logger = logging.getLogger(__name__)


@shared_task(name="default.save_photos")
def save_photos(folder, photos, activity, photographer, public):
    """
    Upload a batch of photos to the server and add them to an activity.

    This task will create and launch a Celery workflow with a new Task for each photo that needs to be uploaded.

    :param folder: The folder that contains the photos to be processed.
    :param photos: List of photo file paths that should be uploaded from the folder.
    :param activity: Which activity to add the photos to.
    :param photographer: Who is the photographer of the photos.
    :param public: If the photo is public or not.

    :return: Dictionary with the number of tasks scheduled:
             {
               'scheduled_tasks': The number of save tasks scheduled.
             }
    """
    logger.info(f"Starting tasks to save {len(photos)} photos for activity {activity.id}")

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

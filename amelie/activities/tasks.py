import logging

from celery import shared_task


logger = logging.getLogger(__name__)


@shared_task()
def save_photos(folder, photos, activity, photographer, public):
    logger.info("Start of save_photos")
    from amelie.files.models import Attachment
    import os
    logger.info(f"Saving {len(photos)} photos...")
    for i, photo in enumerate(photos):
        if i % 10 == 0:
            logger.info(f"[{i+1}/{len(photos)}] Saving photo...")
        file = os.path.join(folder, photo)
        attachment = Attachment(file=file, caption='', owner=photographer, public=public)
        attachment.save(create_thumbnails=True)
        activity.photos.add(attachment)

    # Save new set of photos
    logger.info(f"Adding photos to activity...")
    activity.save()
    logger.info("End of save_photos")

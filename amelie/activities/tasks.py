from celery import shared_task


@shared_task()
def save_photos(folder, photos, activity, photographer, public):
    from amelie.files.models import Attachment
    import os
    for photo in photos:
        file = os.path.join(folder, photo)
        attachment = Attachment(file=file, caption='', owner=photographer, public=public)
        attachment.save()
        activity.photos.add(attachment)

    # Save new set of photos
    activity.save()

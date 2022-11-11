import os

from django.conf import settings
from email.mime.image import MIMEImage


def list_email_images():
    res = []
    for filename in os.listdir(os.path.join(settings.STATIC_ROOT, 'email images')):
        with open(os.path.join(settings.STATIC_ROOT, filename)) as filepointer:
            msg_img = MIMEImage(filepointer.read())
            msg_img.add_header('Content-ID', '<{}>'.format(filename))

            res.append(msg_img)

    return res

import base64
import uuid
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import io
import qrcode
import qrcode.image.svg


class PendingPosToken(models.Model):
    class TokenTypes(models.TextChoices):
        LOGIN = 'login', _("Login token")
        REGISTRATION = 'registration', _("Registration token")

    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, blank=True, null=True, related_name='pending_pos_login_tokens', on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=TokenTypes.choices)
    created_at = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        '''On create, update creation timestamp'''
        # Override save method because then we use the timezone-aware version of datetime.now()
        # See https://stackoverflow.com/questions/1737017/django-auto-now-and-auto-now-add/1737078#1737078
        if not self.created_at:
            self.created_at = timezone.now()
        return super(PendingPosToken, self).save(*args, **kwargs)

    def get_url(self):
        redirect_url = reverse('personal_tab:pos_verify', kwargs={'uuid': str(self.token)})
        return urljoin(settings.ABSOLUTE_PATH_TO_SITE, redirect_url)

    def png_image(self):
        qr = qrcode.make(self.get_url())
        img = io.BytesIO()
        qr.save(img)
        img_txt = base64.b64encode(img.getvalue())
        img.close()
        return (bytes("data:image/jpeg;base64,".encode()) + img_txt).decode()

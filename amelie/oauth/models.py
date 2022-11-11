import uuid
from datetime import timedelta

from django.db import models
from django.urls import reverse

from amelie.members.models import Person


class LoginToken(models.Model):
    EXPIRE_AFTER = timedelta(hours=24)

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('oauth:token_login', kwargs={"token": self.token})

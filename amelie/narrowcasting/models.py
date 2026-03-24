from django.db import models

from amelie.activities.models import Activity


class TelevisionPromotion(models.Model):
    activity = models.ForeignKey(Activity, null=True, blank=True, on_delete=models.SET_NULL)
    attachment = models.ImageField(upload_to='televicie/')
    start = models.DateField()
    end = models.DateField()


class SpotifyAssociation(models.Model):
    name = models.CharField(max_length=191, unique=True)
    access_token = models.TextField(blank=True)
    scopes = models.CharField(max_length=191, blank=True)
    refresh_token = models.TextField(blank=True)

    def __str__(self):
        return self.name

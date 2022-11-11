from django.db import models
from django.utils.translation import get_language, gettext_lazy as _

from amelie.members.models import Person


class PushNotification(models.Model):
    title_en = models.CharField(max_length=50, blank=False, null=False)
    title_nl = models.CharField(max_length=50, blank=False, null=False)

    message_en = models.CharField(max_length=150, blank=False, null=False)
    message_nl = models.CharField(max_length=150, blank=False, null=False)

    json_data = models.JSONField(blank=False, null=True)

    recipients = models.ManyToManyField(Person, blank=True)

    class Meta:
        verbose_name = _('Push Notification')
        verbose_name_plural = _('Push Notifications')

    def __str__(self):
        return '%s' % self.title

    @property
    def title(self):
        language = get_language()
        return self.title_en if language == 'en' else self.title_nl

    @property
    def message(self):
        language = get_language()
        return self.message_en if language == 'en' else self.message_nl

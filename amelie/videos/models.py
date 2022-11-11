from django.urls import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _

from amelie.members.models import Committee
from amelie.videos.managers import VideoManager


class BaseVideo(models.Model):
    video_id = models.CharField(primary_key=True, max_length=40, blank=False, null=False)
    title = models.CharField(max_length=191, blank=False, null=False)
    description = models.TextField()
    date_published = models.DateTimeField(blank=False, null=False)
    thumbnail_url = models.CharField(max_length=191, blank=False, null=False)

    publisher = models.ForeignKey(Committee, on_delete=models.PROTECT)

    is_featured = models.BooleanField(default=False, verbose_name=_('Featured'))
    public = models.BooleanField(default=True, verbose_name=_('Public'))

    objects = VideoManager()

    class Meta:
        ordering = ['-date_published']
        verbose_name = _('Video')
        verbose_name_plural = _('Videos')

    def __str__(self):
        return '%s' % self.title

    def can_edit(self, person):
        mediacie = Committee.objects.get(abbreviation="MediaCie", abolished__isnull=True)
        return person.is_board() or person in mediacie.members() or person.user.is_superuser

    def can_delete(self, person):
        return self.can_edit(person)

    def get_video_type(self):
        if hasattr(self, 'youtubevideo'):
            return "youtube"
        elif hasattr(self, 'streamingiavideo'):
            return "streamingia"
        else:
            return None

    def get_absolute_url(self):
        if hasattr(self, 'youtubevideo'):
            return reverse('videos:single_yt_video', args=(), kwargs={'pk': self.video_id})
        elif hasattr(self, 'streamingiavideo'):
            return reverse('videos:single_ia_video', args=(), kwargs={'pk': self.video_id})
        else:
            return None


class YouTubeVideo(BaseVideo):
    class Meta:
        ordering = ['-date_published']
        verbose_name = _('YouTube video')
        verbose_name_plural = _('YouTube videos')

    def get_absolute_url(self):
        return reverse('videos:single_yt_video', args=(), kwargs={'pk': self.video_id})


class StreamingIAVideo(BaseVideo):
    class Meta:
        ordering = ['-date_published']
        verbose_name = _('Streaming.IA video')
        verbose_name_plural = _('Streaming.IA videos')

    def get_absolute_url(self):
        return reverse('videos:single_ia_video', args=(), kwargs={'pk': self.video_id})

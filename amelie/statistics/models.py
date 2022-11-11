from django.db import models
from django.utils.translation import gettext_lazy as _, gettext


class Hits(models.Model):
    date_start = models.DateField(verbose_name=_("Starts on"))
    date_end = models.DateField(verbose_name=_("Ends on"))
    page = models.CharField(verbose_name=_("Page"), max_length=255)
    user_agent = models.CharField(verbose_name=_("User-Agent"), max_length=255, blank=True)
    hit_count = models.PositiveIntegerField(verbose_name=_("Hits"), default=0)

    def __str__(self):
        return gettext("Hits between {} and {} on page '{}' with User-Agent '{}'".format(
            str(self.date_start),
            str(self.date_end),
            self.page,
            self.user_agent or '(unknown)'
        ))

    class Meta:
        unique_together = [["date_start", "page", "user_agent"]]
        verbose_name = "Hits"
        verbose_name_plural = "Hits"

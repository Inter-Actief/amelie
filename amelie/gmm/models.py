from ckeditor.fields import RichTextField
from django.db import models


class GMM(models.Model):
    date = models.DateField(blank=True, null=True)
    agenda = RichTextField()

    def __str__(self):
        return self.date.__str__()

    class Meta:
        verbose_name = "GMM"
        verbose_name_plural = "GMMs"
        ordering = ["-date"]

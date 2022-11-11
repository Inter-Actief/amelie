from datetime import date

from django.db import models
from django.db.models import Q

class CompanyManager(models.Manager):
    def active(self):
        return self.get_queryset().filter(end_date__gte=date.today(), start_date__lte=date.today())

    def inactive(self):
        return self.get_queryset().filter(Q(end_date__lt=date.today()) | Q(start_date__gt=date.today()))

from django.db import models

from amelie.tools.managers import PublicManagerMixin


class EventManager(models.Manager, PublicManagerMixin):
    pass

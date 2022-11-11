from django.db import models

from amelie.tools.managers import PublicManagerMixin


class PublicationManager(models.Manager, PublicManagerMixin):
    pass

from django.db import models

from amelie.tools.managers import PublicManagerMixin


class VideoManager(models.Manager, PublicManagerMixin):
    pass

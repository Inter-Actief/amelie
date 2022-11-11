from django.db import models

from amelie.tools.managers import PublicManagerMixin


class AttachmentManager(models.Manager, PublicManagerMixin):
    pass

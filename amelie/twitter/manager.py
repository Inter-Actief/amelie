from django.db import models


class TwitterAccountManager(models.Manager):
    def get_queryset(self):
        return super(TwitterAccountManager, self).get_queryset().filter(is_active=True)

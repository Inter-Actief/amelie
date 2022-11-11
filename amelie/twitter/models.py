from django.conf import settings
from django.db import models
from twython import Twython

from amelie.twitter.manager import TwitterAccountManager


class TwitterAccount(models.Model):
    screenname = models.CharField(max_length=100, blank=False, null=False, unique=True)

    oauth_token = models.CharField(max_length=100, blank=True)
    oauth_token_secret = models.CharField(max_length=100, blank=True)

    date_added = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_readonly = models.BooleanField(default=False)

    objects = models.Manager()
    active = TwitterAccountManager()

    #some data to keep track of which tweets we already have
    last_tweet = models.CharField(max_length=25, blank=True)
    last_update = models.DateTimeField(auto_now_add=True)

    #should the stream show in the app
    show_in_app = models.BooleanField(default=True)

    #app specific data
    image_url = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['screenname', 'date_added']

    def __str__(self):
        return str(self.screenname)

    def get_twython_instance(self):
        # Not if we aren't active
        if self.is_active == False:
            raise Exception("Twitter account not active")
        token = self.oauth_token if self.oauth_token else settings.TWITTER_OAUTH_TOKEN
        secret = self.oauth_token_secret if self.oauth_token_secret else settings.TWITTER_OAUTH_SECRET
        # Create a Twython instance
        instance = Twython(
            settings.TWITTER_APP_KEY, settings.TWITTER_APP_SECRET, token, secret
        )

        # Done
        return instance


class Tweet(models.Model):
    account = models.ForeignKey(TwitterAccount, on_delete=models.PROTECT)
    content = models.TextField()
    timestamp = models.DateTimeField()

    def __str__(self):
        return str(self.content)

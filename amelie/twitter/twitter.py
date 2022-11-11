from datetime import datetime, timedelta

from django.utils import timezone

from amelie.twitter.models import TwitterAccount, Tweet

update_interval = timedelta(seconds=300)


def update_streams():
    twitter_accounts = TwitterAccount.objects.filter(is_active=True, last_update__lt=(timezone.now() - update_interval))

    for account in twitter_accounts:
        twython_instance = account.get_twython_instance()
        tweet_set = None
        if account.last_tweet is "":
            tweet_set = twython_instance.get_user_timeline(screen_name=account.screenname, count=20)
        else:
            tweet_set = twython_instance.get_user_timeline(screen_name=account.screenname, since_id=account.last_tweet)

        if(len(tweet_set) > 0):
            account.last_tweet = tweet_set[0]["id"]
            account.image_url = tweet_set[0]["user"]["profile_image_url_https"]
            #twitter uses _normal images as default, we want the big images
            #sadly twitter doesn't provide them in their api format, so we just replace normal with bigger
            account.image_url.replace("normal", "bigger")
        account.last_update = timezone.now()
        account.save()

        utc = timezone.utc
        for raw_tweet in tweet_set:
            date = datetime.strptime(raw_tweet["created_at"], "%a %b %d %H:%M:%S +0000 %Y")
            date = date.replace(tzinfo=utc)
            tweet = Tweet(account=account, content=raw_tweet["text"], timestamp=date)
            tweet.save()

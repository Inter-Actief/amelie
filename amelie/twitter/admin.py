from django.contrib import admin

from amelie.twitter.models import TwitterAccount, Tweet


class TwitterAccountAdmin(admin.ModelAdmin):
    list_display = ('screenname', 'oauth_token', 'is_active', 'date_added',)
    search_fields = ('screenname',)
    list_filter = ('date_added', 'is_active',)
    date_hierarchy = 'date_added'


class TweetAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'account', 'content')
    search_fields = ('account__screenname', 'content', )
    list_filter = ('account',)
    date_hierarchy = 'timestamp'


admin.site.register(TwitterAccount, TwitterAccountAdmin)
admin.site.register(Tweet, TweetAdmin)

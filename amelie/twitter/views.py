from django.shortcuts import render
from django.template import RequestContext, Template
from django.utils.translation import gettext_lazy as _l

from amelie.tools.decorators import require_board
from amelie.twitter.forms import TweetForm


@require_board
def index(request):
    return render(request, 'twitter_index.html', locals())


@require_board
def new_tweet(request):
    form = TweetForm(data=request.POST or None)
    preview = None
    max_length = 140

    if request.method == "POST":
        if form.is_valid() and request.POST.get('preview', None):
            preview = Template(form.cleaned_data['template']).render(RequestContext(request, {}))
        elif form.is_valid():
            if form.send_tweet():
                message = _l('The tweet has been sent!')
            else:
                message = _l('Unfortunately, an error occurred.')

            return render(request, 'message.html', locals())

    return render(request, 'twitter_new_tweet.html', locals())

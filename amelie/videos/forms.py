from django import forms
from django.utils.translation import gettext_lazy as _

from amelie.activities.forms import DateTimeSelector, SplitDateTimeField
from amelie.tools import youtube
from amelie.tools import streaming_ia
from .models import YouTubeVideo, StreamingIAVideo


def validate_youtube_video_id(video_id):
    video = youtube.retrieve_video_details(video_id)
    if not video:
        raise forms.ValidationError(_('YouTube video with ID "%(video_id)s" doesn\'t exist.'), params={
            'video_id': video_id
        })


def validate_streaming_video_id(video_id):
    video = streaming_ia.retrieve_video_details(video_id)
    if not video:
        raise forms.ValidationError(_('Streaming.IA video with ID "%(video_id)s" doesn\'t exist.'), params={
            'video_id': video_id
        })


class YouTubeVideoForm(forms.ModelForm):
    video_id = forms.CharField(max_length=20, validators=[validate_youtube_video_id])

    class Meta:
        model = YouTubeVideo
        fields = ('video_id', 'publisher', "public", 'is_featured')


class YouTubeVideoProcessedForm(forms.ModelForm):
    class Meta:
        model = YouTubeVideo
        fields = ('date_published', 'publisher', "public", 'is_featured')
        field_classes = {'date_published': SplitDateTimeField}
        widgets = {'date_published': DateTimeSelector}


class StreamingVideoForm(forms.ModelForm):
    video_id = forms.CharField(max_length=20, validators=[validate_streaming_video_id])

    class Meta:
        model = StreamingIAVideo
        fields = ('video_id', 'publisher', "public", 'is_featured')


class StreamingVideoProcessedForm(forms.ModelForm):
    class Meta:
        model = StreamingIAVideo
        fields = ('date_published', 'publisher', "public", 'is_featured')
        field_classes = {'date_published': SplitDateTimeField}
        widgets = {'date_published': DateTimeSelector}

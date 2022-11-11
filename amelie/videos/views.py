from json import JSONDecodeError

from dateutil import parser
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, DetailView, DeleteView, UpdateView, CreateView
from googleapiclient.errors import Error as googleapiclient_Error
from oauth2client.client import Error as oauth2client_Error
from requests.exceptions import ConnectionError as RequestsConnectionError

from amelie.members.models import Committee
from amelie.tools.mixins import RequireCommitteeMixin
from amelie.tools import youtube
from amelie.tools import streaming_ia

from .models import BaseVideo, YouTubeVideo, StreamingIAVideo
from .forms import YouTubeVideoForm, YouTubeVideoProcessedForm, StreamingVideoForm, StreamingVideoProcessedForm


class VideoList(ListView):
    template_name = "videos/videos.html"
    model = BaseVideo
    paginate_by = 9

    def get_queryset(self):
        return self.model.objects.filter_public(self.request)

    def get_context_data(self, **kwargs):
        context = super(VideoList, self).get_context_data(**kwargs)
        if hasattr(self.request, 'person'):
            person = self.request.person
            mediacie = Committee.objects.get(abbreviation="MediaCie", abolished__isnull=True)
            can_create = person.is_board() or person in mediacie.members() or person.user.is_superuser
            context['can_create'] = can_create

        return context


class YoutubeVideoDetail(DetailView):
    template_name = "videos/yt_video.html"
    model = YouTubeVideo

    def get_context_data(self, **kwargs):
        context = super(YoutubeVideoDetail, self).get_context_data(**kwargs)

        if hasattr(self.request, 'person'):
            obj = self.get_object()
            context['edit_allowed'] = obj.can_edit(self.request.person)
            context['delete_allowed'] = obj.can_delete(self.request.person)

        return context

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.public and (not hasattr(request, 'user') or not request.user.is_authenticated):
            return redirect('videos:list_videos')

        return super(YoutubeVideoDetail, self).get(request, *args, **kwargs)


class StreamingVideoDetail(DetailView):
    template_name = "videos/ia_video.html"
    model = StreamingIAVideo

    def get_context_data(self, **kwargs):
        context = super(StreamingVideoDetail, self).get_context_data(**kwargs)

        context['streaming_base_url'] = settings.STREAMING_BASE_URL

        if hasattr(self.request, 'person'):
            obj = self.get_object()
            context['edit_allowed'] = obj.can_edit(self.request.person)
            context['delete_allowed'] = obj.can_delete(self.request.person)

        return context

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.public and (not hasattr(request, 'user') or not request.user.is_authenticated):
            return redirect('videos:list_videos')

        return super(StreamingVideoDetail, self).get(request, *args, **kwargs)


class VideoDelete(RequireCommitteeMixin, DeleteView):
    model = BaseVideo
    template_name = 'videos/video_delete.html'
    success_url = reverse_lazy('videos:list_videos')
    abbreviation = "MediaCie"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.can_delete(request.person):
            return redirect(obj)

        return super(VideoDelete, self).dispatch(request, *args, **kwargs)


class YoutubeVideoUpdate(RequireCommitteeMixin, UpdateView):
    model = YouTubeVideo
    template_name = "videos/yt_video_form.html"
    abbreviation = "MediaCie"
    form_class = YouTubeVideoProcessedForm

    def get_form(self, form_class=None):
        form = super(YoutubeVideoUpdate, self).get_form(form_class=form_class)
        if not self.request.is_board:
            form.fields['publisher'].queryset = self.request.person.current_committees()

        return form

    def form_valid(self, form):
        video = form.save(commit=False)

        # Do some YouTube API data processing
        yt_details = youtube.retrieve_video_details(video.video_id)
        video.title = yt_details['title']
        video.description = yt_details['description']
        video.thumbnail_url = yt_details['thumbnails']['standard']['url'] if 'standard' in yt_details['thumbnails'] \
            else yt_details['thumbnails']['default']['url']

        video.save()
        return redirect(video.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super(YoutubeVideoUpdate, self).get_context_data(**kwargs)
        context['is_new'] = False
        return context

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.can_edit(request.person):
            return redirect(obj)

        return super(YoutubeVideoUpdate, self).get(request, *args, **kwargs)


class StreamingVideoUpdate(RequireCommitteeMixin, UpdateView):
    model = StreamingIAVideo
    template_name = "videos/ia_video_form.html"
    abbreviation = "MediaCie"
    form_class = StreamingVideoProcessedForm

    def get_form(self, form_class=None):
        form = super(StreamingVideoUpdate, self).get_form(form_class=form_class)
        if not self.request.is_board:
            form.fields['publisher'].queryset = self.request.person.current_committees()

        return form

    def form_valid(self, form):
        video = form.save(commit=False)

        # Do some Streaming.IA API data processing
        ia_details = streaming_ia.retrieve_video_details(video.video_id)
        video.title = ia_details['videoName']
        video.description = ia_details['description'] or "-"
        video.thumbnail_url = f"{settings.STREAMING_BASE_URL}/{ia_details['thumbnailLocation']}"

        video.save()
        return redirect(video.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super(StreamingVideoUpdate, self).get_context_data(**kwargs)
        context['is_new'] = False
        return context

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.can_edit(request.person):
            return redirect(obj)

        return super(StreamingVideoUpdate, self).get(request, *args, **kwargs)


class YoutubeVideoCreate(RequireCommitteeMixin, CreateView):
    model = YouTubeVideo
    template_name = "videos/yt_video_form.html"
    form_class = YouTubeVideoForm
    abbreviation = "MediaCie"

    def get_form(self, form_class=None):
        form = super(YoutubeVideoCreate, self).get_form(form_class=form_class)
        mediacie = Committee.objects.get(abbreviation="MediaCie", abolished__isnull=True)

        video_id = None
        if 'video_id' in self.kwargs:
            video_id = self.kwargs['video_id']

        if video_id is not None:
            form.fields['video_id'].initial = video_id

        if self.request.person in mediacie.members():
            form.fields['publisher'].initial = mediacie
        if not self.request.is_board:
            form.fields['publisher'].queryset = self.request.person.current_committees()

        return form

    def get(self, request, *args, **kwargs):
        try:
            return super(YoutubeVideoCreate, self).get(request, *args, **kwargs)
        except (googleapiclient_Error, oauth2client_Error):
            #from raven.contrib.django.raven_compat.models import client
            #client.captureException()

            messages.error(request, _("Could not connect to Youtube! "
                                      "Please contact the WWW committee if this problem persists."))
            return redirect("videos:list_videos")

    def get_context_data(self, **kwargs):
        context = super(YoutubeVideoCreate, self).get_context_data(**kwargs)

        listed_ids = YouTubeVideo.objects.values_list('pk', flat=True)
        recent_uploads = youtube.retrieve_channel_video_list()
        context['filtered_uploads'] = [v for v in recent_uploads if v['snippet']['resourceId']['videoId'] not in listed_ids][:5]
        context['is_new'] = True

        return context

    def form_valid(self, form):
        video = form.save(commit=False)

        # Do some YouTube API data processing
        yt_details = youtube.retrieve_video_details(video.video_id)
        video.title = yt_details['title']
        video.description = yt_details['description']
        video.date_published = yt_details['publishedAt']
        video.thumbnail_url = yt_details['thumbnails']['standard']['url'] if 'standard' in yt_details['thumbnails'] \
            else yt_details['thumbnails']['high']['url']

        video.save()
        return redirect(video.get_absolute_url())


class StreamingVideoCreate(RequireCommitteeMixin, CreateView):
    model = StreamingIAVideo
    template_name = "videos/ia_video_form.html"
    form_class = StreamingVideoForm
    abbreviation = "MediaCie"

    def get_form(self, form_class=None):
        form = super(StreamingVideoCreate, self).get_form(form_class=form_class)
        mediacie = Committee.objects.get(abbreviation="MediaCie", abolished__isnull=True)

        video_id = None
        if 'video_id' in self.kwargs:
            video_id = self.kwargs['video_id']

        if video_id is not None:
            form.fields['video_id'].initial = video_id

        if self.request.person in mediacie.members():
            form.fields['publisher'].initial = mediacie
        if not self.request.is_board:
            form.fields['publisher'].queryset = self.request.person.current_committees()

        return form

    def get(self, request, *args, **kwargs):
        try:
            return super(StreamingVideoCreate, self).get(request, *args, **kwargs)
        except (RequestsConnectionError, JSONDecodeError):
            #from raven.contrib.django.raven_compat.models import client
            #client.captureException()

            messages.error(request, _("Could not connect to Streaming.IA! "
                                      "Please contact the WWW committee if this problem persists."))
            return redirect("videos:list_videos")

    def get_context_data(self, **kwargs):
        context = super(StreamingVideoCreate, self).get_context_data(**kwargs)

        listed_ids = StreamingIAVideo.objects.values_list('pk', flat=True)
        recent_uploads = streaming_ia.retrieve_video_list()
        context['filtered_uploads'] = [v for v in recent_uploads if str(v['id']) not in listed_ids][:5]
        context['is_new'] = True

        return context

    def form_valid(self, form):
        video = form.save(commit=False)

        # Do some Streaming.IA API data processing
        ia_details = streaming_ia.retrieve_video_details(video.video_id)
        video.title = ia_details['videoName']
        video.description = ia_details['description'] or "-"
        video.date_published = make_aware(parser.parse(ia_details['videoDate']))
        video.thumbnail_url = f"{settings.STREAMING_BASE_URL}/{ia_details['thumbnailLocation']}"

        video.save()
        return redirect(video.get_absolute_url())

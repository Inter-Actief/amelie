import logging

import requests
from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page

from amelie.narrowcasting.models import SpotifyAssociation


def index(request):
    return render(request, 'index.html', locals())


def room(request):
    if request.GET.get('setup_spotify', None) is not None:
        if settings.SPOTIFY_CLIENT_SECRET == "":
            raise ValueError(_("Spotify settings not configured."))

        identifier = request.GET.get('setup_spotify')
        try:
            assoc = SpotifyAssociation.objects.get(name=identifier)
            if assoc.refresh_token:
                raise ValueError(_("Association already exists."))
        except SpotifyAssociation.DoesNotExist:
            # Create bare association and redirect
            SpotifyAssociation.objects.create(name=identifier)
        return_url = reverse('narrowcasting:room_spotify_callback')
        return_url = request.build_absolute_uri(return_url)
        return redirect(to="https://accounts.spotify.com/authorize?client_id={}&response_type=code&redirect_uri={}&state={}&scope={}".format(
            settings.SPOTIFY_CLIENT_ID, return_url, identifier, settings.SPOTIFY_SCOPES
        ))

    return render(request, 'room.html')

def room_spotify_callback(request):
    auth_code = request.GET.get("code", None)
    state = request.GET.get("state", None)
    if settings.SPOTIFY_CLIENT_SECRET == "":
        raise ValueError(_("Spotify settings not configured."))

    if auth_code is None or state is None:
        raise ValueError(_("No auth code or state given."))

    try:
        association = SpotifyAssociation.objects.get(name=state)
    except SpotifyAssociation.DoesNotExist:
        raise ValueError(_("No such authentication attempt found, try again."))

    return_url = reverse('narrowcasting:room_spotify_callback')
    return_url = request.build_absolute_uri(return_url)

    try:
        res = requests.post("https://accounts.spotify.com/api/token", data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": return_url,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET
        })
    except requests.exceptions.ConnectionError as e:
        raise ValueError(_("ConnectionError while refreshing access token:") + f" {e}")

    data = res.json()
    try:
        association.access_token = data['access_token']
        association.scopes = data['scope']
        association.refresh_token = data['refresh_token']
        association.save()
    except KeyError:
        if 'error' in data:
            raise ValueError(data['error_description'])

    return redirect("narrowcasting:room")


def _spotify_refresh_token(association):
    try:
        res = requests.post("https://accounts.spotify.com/api/token", data={
            "grant_type": "refresh_token",
            "refresh_token": association.refresh_token,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET
        })
    except requests.exceptions.ConnectionError as e:
        raise ValueError(_("ConnectionError while refreshing access token:") + f" {e}")

    data = res.json()

    if 'error' in data:
        raise ValueError(data['error_description'])
    elif res.status_code != 200:
        raise ValueError(f"Status code: {res.status_code}")

    try:
        association.access_token = data['access_token']
        association.save()
    except KeyError as e:
        if 'error' in data:
            raise ValueError(data['error_description'])
        else:
            raise e
    return association

@cache_page(15)
def room_spotify_now_playing(request):
    identifier = request.GET.get('id', None)
    if settings.SPOTIFY_CLIENT_SECRET == "":
        raise ValueError(_("Spotify settings not configured."))

    if identifier is None:
        raise ValueError(_("Missing identifier"))

    try:
        assoc = SpotifyAssociation.objects.get(name=identifier)
    except SpotifyAssociation.DoesNotExist:
        raise Http404(_("No association for this identifier"))

    try:
        res = requests.get("https://api.spotify.com/v1/me/player",
                            params={"market": "from_token"},
                            headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                            )
    except requests.exceptions.ConnectionError as e:
        log = logging.getLogger("amelie.narrowcasting.views.room_spotify_now_playing")
        log.warning(f"ConnectionError while retrieving player info: {e}")
        # Return empty response
        return JsonResponse({})

    if res.status_code == 200:
        data = res.json()
        data['error'] = False
    elif res.status_code == 204:
        data = {'error': False, 'is_playing': False}
    elif res.status_code == 401:
        # Access code expired, request a new one and retry the request.
        try:
            _spotify_refresh_token(assoc)
            return room_spotify_now_playing(request)
        except ValueError as e:
            data = {'error': True, 'code': 500, 'msg': str(e)}
    elif res.status_code == 429:
        # Since we often exceed the rate limit, do not report as error
        data = {'error': False, 'is_playing': False}
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}

    return JsonResponse(data)


@cache_page(15)
def room_spotify_pause(request):
    identifier = request.GET.get('id', None)
    if settings.SPOTIFY_CLIENT_SECRET == "":
        raise ValueError(_("Spotify settings not configured."))

    if identifier is None:
        raise ValueError(_("Missing identifier"))

    try:
        assoc = SpotifyAssociation.objects.get(name=identifier)
    except SpotifyAssociation.DoesNotExist:
        raise Http404(_("No association for this identifier"))

    try:
        res = requests.put("https://api.spotify.com/v1/me/player/pause",
                            headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                            )
    except requests.exceptions.ConnectionError as e:
        log = logging.getLogger("amelie.narrowcasting.views.room_spotify_now_playing")
        log.warning(f"ConnectionError while pausing Spotify player: {e}")
        # Return empty response
        return JsonResponse({})

    if res.status_code == 200:
        data = res.json()
        data['error'] = False
    elif res.status_code == 204:
        data = {'error': False, 'is_playing': False}
    elif res.status_code == 401:
        # Access code expired, request a new one and retry the request.
        try:
            _spotify_refresh_token(assoc)
            return room_spotify_pause(request)
        except ValueError as e:
            data = {'error': True, 'code': 500, 'msg': str(e)}
    elif res.status_code == 429:
        # Since we often exceed the rate limit, do not report as error
        data = {'error': False, 'is_playing': False}
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}

    return JsonResponse(data)


@cache_page(15)
def room_spotify_play(request):
    identifier = request.GET.get('id', None)
    if settings.SPOTIFY_CLIENT_SECRET == "":
        raise ValueError(_("Spotify settings not configured."))

    if identifier is None:
        raise ValueError(_("Missing identifier"))

    try:
        assoc = SpotifyAssociation.objects.get(name=identifier)
    except SpotifyAssociation.DoesNotExist:
        raise Http404(_("No association for this identifier"))

    try:
        res = requests.put("https://api.spotify.com/v1/me/player/play",
                            headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                            )
    except requests.exceptions.ConnectionError as e:
        log = logging.getLogger("amelie.narrowcasting.views.room_spotify_now_playing")
        log.warning(f"ConnectionError while unpausing Spotify player: {e}")
        # Return empty response
        return JsonResponse({})

    if res.status_code == 200:
        data = res.json()
        data['error'] = False
    elif res.status_code == 204:
        data = {'error': False, 'is_playing': False}
    elif res.status_code == 401:
        # Access code expired, request a new one and retry the request.
        try:
            _spotify_refresh_token(assoc)
            return room_spotify_play(request)
        except ValueError as e:
            data = {'error': True, 'code': 500, 'msg': str(e)}
    elif res.status_code == 429:
        # Since we often exceed the rate limit, do not report as error
        data = {'error': False, 'is_playing': False}
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}


    return JsonResponse(data)

import datetime
import logging
from typing import Any, List, Dict

import markdown
import requests
from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from mautrix.client import ClientAPI
from mautrix.types import PaginationDirection, RoomEventFilter, PaginatedMessages, TextMessageEventContent, \
    MessageEvent, Format, RoomID, UserID
from mautrix.types.event.type import EventType

from amelie.narrowcasting.models import SpotifyAssociation
from amelie.tools.asyncio import get_event_loop


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
    except (requests.exceptions.ConnectionError, ConnectionError) as e:
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
    except (requests.exceptions.ConnectionError, ConnectionError) as e:
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
    except (requests.exceptions.ConnectionError, ConnectionError) as e:
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
    except (requests.exceptions.ConnectionError, ConnectionError) as e:
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
    except (requests.exceptions.ConnectionError, ConnectionError) as e:
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


@cache_page(15)
def room_ia_chat(request):
    try:
        messages = get_event_loop().run_until_complete(_get_ia_chat_messages())
        return JsonResponse({'error': False, 'messages': messages})
    except Exception as e:
        return JsonResponse({'error': True, 'messages': [], 'error_msg': str(e)})


async def _get_ia_chat_messages() -> List[Dict[str, Any]]:
    matrix_hostname = settings.MATRIX_SETTINGS['SERVER']
    access_token = settings.MATRIX_SETTINGS['TOKEN']
    user_id = settings.MATRIX_SETTINGS['USER']
    chat_room_id = settings.MATRIX_SETTINGS['ROOM_ID']
    max_msg_to_show = settings.MATRIX_SETTINGS['MAX_MSG_TO_SHOW']
    max_msg_length = settings.MATRIX_SETTINGS['MAX_MSG_LENGTH']

    if matrix_hostname == "" or access_token == "" or chat_room_id == "":
        raise ValueError("Chat settings not configured.")

    client: ClientAPI = ClientAPI(user_id, base_url=matrix_hostname, token=access_token)

    try:
        filter_messages = RoomEventFilter(types=[EventType.ROOM_MESSAGE])
        events = await client.get_messages(chat_room_id, direction=PaginationDirection.BACKWARD,
                                           limit=max_msg_to_show, filter_json=filter_messages)

        messages = []
        for ev in events.events:
            ev: MessageEvent
            try:
                username = await _get_user_display_name(client, ev.sender)
                if username is None:
                    username, _ = ClientAPI.parse_user_id(ev.sender)
            except ValueError:
                username = ev.sender
            try:
                timestamp = datetime.datetime.fromtimestamp(ev.timestamp / 1000)
                if timestamp.date() != datetime.date.today():
                    timestamp = timestamp.strftime("%m-%d %H:%M:%S")
                else:
                    timestamp = timestamp.strftime('%H:%M:%S')
            except ValueError:
                timestamp = datetime.datetime.now().strftime('%H:%M:%S')

            if isinstance(ev.content, TextMessageEventContent):
                msg_body = str(ev.content.body)
                if len(msg_body) > max_msg_length:
                    msg_body = msg_body[:max_msg_length].strip() + "…"
            else:
                msg_body = f"<unsupported message '{ev.content.__class__.__name__}'>"

            # Escape the values because they will be rendered in the frontend without escaping
            username = escape(username)
            msg_body = escape(msg_body)

            messages.append({"from": username, "time": timestamp, "message": msg_body})
    finally:
        if client and client.api and client.api.session:
            await client.api.session.close()

    return messages[::-1]


async def _get_user_display_name(client: ClientAPI, matrix_id: UserID) -> str:
    return await client.get_displayname(matrix_id)

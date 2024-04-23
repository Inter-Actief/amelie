import requests
from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import cache_page
from requests.auth import HTTPBasicAuth
from django.utils.translation import gettext as _

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


@cache_page(2 * 60)
def room_pcstatus(request):
    api_url = settings.ICINGA_API_HOST

    if settings.ICINGA_API_PASSWORD == "":
        raise ValueError(_("Icinga settings not configured."))

    simple_hosts = ["lusky", "stoetenwolf", "guus"]
    workstations = ["omaduck", "katrien", "cornelis", "prul", "gideon", "woerd", "dagobert", "martje",
                    "kwik", "kwek", "kwak", "lizzy"]

    try:
        res = requests.get(api_url + "objects/hosts", verify=settings.ICINGA_API_SSL_VERIFY,
                           auth=HTTPBasicAuth(settings.ICINGA_API_USERNAME, settings.ICINGA_API_PASSWORD))
        hosts = [x for x in res.json()['results'] if x['name'] in simple_hosts or x['name'] in workstations]

        res = requests.get(api_url + "objects/services", verify=settings.ICINGA_API_SSL_VERIFY,
                           auth=HTTPBasicAuth(settings.ICINGA_API_USERNAME, settings.ICINGA_API_PASSWORD))
        services = [x for x in res.json()['results'] if x['attrs']['host_name'] in workstations]
    except requests.exceptions.ConnectionError:
        return JsonResponse({})

    host_data = {}
    for host in hosts:
        host_data[host['name']] = host['attrs']
        host_data[host['name']]['services'] = []

    for service in services:
        if service['attrs']['host_name'] in host_data.keys():
            host_data[service['attrs']['host_name']]['services'].append(service)

    # Construct a simple dict with only the info we need
    result = {}
    for host in host_data.keys():
        data = host_data[host]

        isup = not data['last_check_result']['output'].startswith("PING CRITICAL")

        login_service_status = None
        user = None
        for service in data['services']:
            if service['attrs']['display_name'] == "Logged in user":
                login_service_status = service['attrs']['last_check_result']['output']
        if login_service_status is not None:
            if login_service_status.startswith("OK: No one logged in"):
                user = None
            elif login_service_status.startswith("OK:") and login_service_status.endswith("is logged in."):
                user = login_service_status.replace("OK:", "").replace("is logged in.", "").strip()

        if isup:
            result[host] = "on"
            if user is not None:
                if user.lower() == "visitor":
                    result[host] = "guest"
                else:
                    result[host] = "user"
        else:
            result[host] = "off"

    return JsonResponse(result)


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

    res = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": return_url,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET
    })

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
    res = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "refresh_token",
        "refresh_token": association.refresh_token,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET
    })

    data = res.json()
    try:
        association.access_token = data['access_token']
        association.save()
    except KeyError:
        if 'error' in data:
            raise ValueError(data['error_description'])
    return association

@cache_page(5)
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

    res = requests.get("https://api.spotify.com/v1/me/player",
                        params={"market": "from_token"},
                        headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                        )
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
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}

    return JsonResponse(data)


@cache_page(5)
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

    res = requests.put("https://api.spotify.com/v1/me/player/pause",
                        headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                        )
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
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}

    return JsonResponse(data)


@cache_page(5)
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

    res = requests.put("https://api.spotify.com/v1/me/player/play",
                        headers={"Authorization": "Bearer {}".format(assoc.access_token)}
                        )
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
    else:
        data = {'error': True, 'code': res.status_code, 'msg': res.content.decode()}

    return JsonResponse(data)

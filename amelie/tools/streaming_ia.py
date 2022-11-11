import requests
from django.conf import settings


def retrieve_video_details(video_id):
    response = requests.get(f"{settings.STREAMING_BASE_URL}/apiv1/video/{video_id}").json()
    if len(response['results']) == 0:
        return None
    return response['results'][0]


def retrieve_video_list():
    response = requests.get(f"{settings.STREAMING_BASE_URL}/apiv1/video/").json()
    return response['results']



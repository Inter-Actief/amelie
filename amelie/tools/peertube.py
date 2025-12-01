import requests
from django.conf import settings


def retrieve_video_details(video_id):
    response = requests.get(f"{settings.PEERTUBE_BASE_URL}/api/v1/videos/{video_id}").json()
    if isinstance(response, dict) and len(response.keys()) == 0:
        return None
    return response

def retrieve_video_list():
    response = requests.get(f"{settings.PEERTUBE_BASE_URL}/api/v1/videos/").json()
    return response['data']

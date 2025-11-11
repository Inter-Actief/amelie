from django.conf import settings

from googleapiclient.discovery import build


def retrieve_video_details(video_id):
    service = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)
    service_list_response = service.videos().list(
        id=video_id,
        part='snippet',
        fields='items(snippet(description,publishedAt,thumbnails/high,thumbnails/standard,thumbnails/default,title))',
    ).execute()

    if len(service_list_response['items']) == 0:
        return None

    return service_list_response['items'][0]['snippet']


def retrieve_channel_video_list():
    service = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)
    service_list_channel_response = service.playlistItems().list(
        part='snippet',
        maxResults=10,
        playlistId=settings.YOUTUBE_UPLOADS_LIST_ID,
        fields='items(snippet(resourceId/videoId,title))',
    ).execute()

    return service_list_channel_response['items']



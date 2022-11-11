from jsonrpc import jsonrpc_method

from amelie.api.decorators import authentication_optional
from amelie.api.exceptions import PermissionDeniedError
from amelie.videos.models import YouTubeVideo


def get_basic_result(video):
    return {
        "id": video.video_id,
        "title": video.title,
        "thumbnail": video.thumbnail_url,
        "featured": video.is_featured,
        "date": video.date_published.isoformat(),
        "publisher": {
            "id": video.publisher.id,
            "name": video.publisher.name
        } if video.publisher else None,
    }

@jsonrpc_method('videos.getVideoStream(Number, Number) -> Array', validate=True)
@jsonrpc_method('getVideoStream(Number, Number) -> Array', validate=True)
@authentication_optional()
def get_video_stream(request, offset, length, authentication=None):
    authenticated = authentication is not None

    videos = YouTubeVideo.objects.filter_public(not authenticated).order_by('-date_published')[offset:length + offset]

    result = []

    for video in videos:
        result.append(get_basic_result(video))

    return result


@jsonrpc_method('videos.getVideoDetails(String) -> Object', validate=True)
@jsonrpc_method('getVideoDetails(String) -> Object', validate=True)
@authentication_optional()
def get_video_details(request, video_id, authentication=None):
    authenticated = authentication is not None

    video = YouTubeVideo.objects.get(video_id=video_id)

    if not video.public and not authenticated:
        raise PermissionDeniedError()

    result = get_basic_result(video)
    result["description"] = video.description if video.description else None

    return result

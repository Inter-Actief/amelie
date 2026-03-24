from typing import List, Dict

from modernrpc import RpcRequestContext

from amelie.api.api import api_server
from amelie.api.authentication_types import AnonymousAuthentication
from amelie.api.decorators import auth_optional
from amelie.api.exceptions import PermissionDeniedError, DoesNotExistError
from amelie.videos.models import BaseVideo


def get_basic_result(video):
    if hasattr(video, 'streamingiavideo'):
        video_type = "ia"
    elif hasattr(video, 'peertubeiavideo'):
        video_type = "pt"
    else:
        video_type = "yt"
    return {
        "id": video.video_id,
        "type": video_type,
        "title": video.title,
        "thumbnail": video.thumbnail_url,
        "featured": video.is_featured,
        "date": video.date_published.isoformat(),
        "publisher": {
            "id": video.publisher.id,
            "name": video.publisher.name
        } if video.publisher else None,
    }


@api_server.register_procedure(name='getVideoStream', auth=auth_optional, context_target='ctx')
def get_video_stream(offset: int, length: int, ctx: RpcRequestContext = None, **kwargs) -> List[Dict]:
    """
    Retrieves various types ('youtube', 'ia') of videos from the website.

    **Module**: `video`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - offset: The index offset into the list of videos to start returning results from.
        - length: The amount of videos to return (maximum 250, will be limited if higher)

    **Return:**
      `List[Dict]`: An array of dictionaries containing the requested videos.

      Each returned element in the list has the following fields:

        - id: The identifier for this video
        - type: The type of video, one of "yt" (YouTube), "ia" (Streaming.IA), or "pt" (PeerTube)
        - title: The title of this video
        - thumbnail: The URL to the thumbnail of this video
        - featured: Boolean, true if the video is currently being featured, false if not.
        - date: The date this video was published (RFC3339)
        - publisher: A dictionary containing information about the publishing committee, can be null:
          - id: ID of the publishing committee
          - name: Name of the publishing committee

    **Example:**

        --> {"method":"getVideoStream", "params":[0, 3]}
        <-- {"result": [{
               "id": "a1b2d4F6",
               "type": "yt",
               "title": "Rially Aftermovie 2020",
               "thumbnail": "https://pbs.twimg.com/profile_image.png",
               "featured": false,
               "date": "2021-12-08T13:00:00+00:00",
               "publisher": {
                 "id": 16,
                 "name": "Board"
               }
             }, {
               "id": "27",
               "type": "ia",
               "title": "SummerSounds 2022",
               "thumbnail": "https://streaming.ia.utwente.nl/videos/27/27",
               "featured": true,
               "date": "2022-09-06T13:00:00+00:00",
               "publisher": {
                 "id": 17,
                 "name": "MedIA"
               }
             }, {...}]
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)

    if length > 250:
        length = 250

    videos = BaseVideo.objects.filter_public(not is_authenticated).order_by('-date_published')[offset:length + offset]

    result = []

    for video in videos:
        result.append(get_basic_result(video))

    return result


@api_server.register_procedure(name='getVideoDetails', auth=auth_optional, context_target='ctx')
def get_video_details(video_id: str, ctx: RpcRequestContext = None, **kwargs) -> Dict:
    """
    Retrieves details for a specific video from the website.

    **Module**: `video`

    **Authentication:** OPTIONAL (Scope: _any_)

    **Parameters:**
      This method accepts the following parameters:

        - video_id: The identifier of the video to retrieve.

    **Return:**
      `Dict`: A dictionary containing the requested video details.

      Each returned element in the list has the following fields:

        - id: The identifier for this video
        - type: The type of video, one of "yt" (YouTube), "ia" (Streaming.IA), or "pt" (PeerTube)
        - title: The title of this video
        - thumbnail: The URL to the thumbnail of this video
        - featured: Boolean, true if the video is currently being featured, false if not.
        - date: The date this video was published (RFC3339)
        - publisher: A dictionary containing information about the publishing committee, can be null:
          - id: ID of the publishing committee
          - name: Name of the publishing committee
        - description: The video description as a string, or null.

    **Raises:**

      DoesNotExistError: The video with this ID does not exist.

    **Example:**

        --> {"method":"getVideoDetails", "params":["a1b2d4F6"]}
        <-- {"result": {
               "id": "a1b2d4F6",
               "type": "yt",
               "title": "Rially Aftermovie 2020",
               "thumbnail": "https://pbs.twimg.com/profile_image.png",
               "featured": false,
               "date": "2021-12-08T13:00:00+00:00",
               "publisher": {
                 "id": 16,
                 "name": "Board"
               },
               "description": null
             }
        }

        --> {"method":"getVideoDetails", "params":["27"]}
        <-- {"result": {
               "id": "27",
               "type": "ia",
               "title": "SummerSounds 2022",
               "thumbnail": "https://streaming.ia.utwente.nl/videos/27/27",
               "featured": true,
               "date": "2022-09-06T13:00:00+00:00",
               "publisher": {
                 "id": 17,
                 "name": "MedIA"
               },
               "description": "On the last Friday..."
             }
        }
    """
    authentication = ctx.auth_result
    is_authenticated = authentication and not isinstance(authentication, AnonymousAuthentication)

    try:
        video = BaseVideo.objects.get(video_id=video_id)
    except BaseVideo.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if not video.public and not is_authenticated:
        raise PermissionDeniedError()

    result = get_basic_result(video)
    result["description"] = video.description if video.description else None

    return result


@api_server.register_procedure(name='videos.getVideoStream', auth=auth_optional, context_target='ctx')
def get_video_stream_2(offset: int, length: int, ctx: RpcRequestContext = None, **kwargs):
    """Alias of `getVideoStream` for backwards compatibility."""
    return get_video_stream(offset=offset, length=length, ctx=ctx, **kwargs)

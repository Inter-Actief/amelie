from typing import List, Dict

from amelie.api.decorators import authentication_optional
from amelie.api.exceptions import PermissionDeniedError, DoesNotExistError
from amelie.videos.models import BaseVideo

from modernrpc.core import rpc_method


def get_basic_result(video):
    return {
        "id": video.video_id,
        "type": "ia" if hasattr(video, 'streamingiavideo') else "yt",
        "title": video.title,
        "thumbnail": video.thumbnail_url,
        "featured": video.is_featured,
        "date": video.date_published.isoformat(),
        "publisher": {
            "id": video.publisher.id,
            "name": video.publisher.name
        } if video.publisher else None,
    }


@rpc_method(name='getVideoStream')
@authentication_optional()
def get_video_stream(offset: int, length: int, **kwargs) -> List[Dict]:
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
        - type: The type of video, one of "yt" (YouTube) or "ia" (Streaming.IA)
        - title: The title of this video
        - thumbnail: The URL to the thumbnail of this video
        - featured: Boolean, true if the video is currently being featured, false if not.
        - date: The date this video was published (RFC3339)
        - publisher: A dictionary containing information about the publishing committee, including the following fields:
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
    authenticated = kwargs.get('authentication') is not None

    if length > 250:
        length = 250

    videos = BaseVideo.objects.filter_public(not authenticated).order_by('-date_published')[offset:length + offset]

    result = []

    for video in videos:
        result.append(get_basic_result(video))

    return result


@rpc_method(name='getVideoDetails')
@authentication_optional()
def get_video_details(video_id: str, **kwargs) -> Dict:
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
        - type: The type of video, one of "yt" (YouTube) or "ia" (Streaming.IA)
        - title: The title of this video
        - thumbnail: The URL to the thumbnail of this video
        - featured: Boolean, true if the video is currently being featured, false if not.
        - date: The date this video was published (RFC3339)
        - publisher: A dictionary containing information about the publishing committee, including the following fields:
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
    authenticated = kwargs.get('authentication') is not None

    try:
        video = BaseVideo.objects.get(video_id=video_id)
    except BaseVideo.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    if not video.public and not authenticated:
        raise PermissionDeniedError()

    result = get_basic_result(video)
    result["description"] = video.description if video.description else None

    return result


@rpc_method(name='videos.getVideoStream')
@authentication_optional()
def get_video_stream_2(offset: int, length: int, **kwargs):
    """Alias of `getVideoStream` for backwards compatibility."""
    return get_video_stream(offset=offset, length=length, **kwargs)

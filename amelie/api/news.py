import logging
from typing import List, Dict

from amelie.api.exceptions import DoesNotExistError
from amelie.tools.templatetags import md
from amelie.news.models import NewsItem

from modernrpc.core import rpc_method
from modernrpc.exceptions import RPCInvalidParams

logger = logging.getLogger(__name__)


@rpc_method(name='getNewsStream')
def get_news_stream(offset: int, length: int) -> List[Dict]:
    """
    Retrieves various types ('web', 'education') of news articles from the website.

    **Module**: `news`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - offset: The index offset into the list of news items to start returning results from.
        - length: The amount of news items to return (maximum 250, will be limited if higher)

    **Return:**
      `List[Dict]`: An array of dictionaries containing the requested news items.

      Each returned element in the list has the following fields:

        - id: The identifier for this news item
        - title: The title of this item
        - category: The category of this news item
        - date: The publication date of this item (RFC3339)
        - author: The name of the person who wrote this item
        - source: A dictionary containing information about the publishing committee, including the following fields:
          - id: ID of the publishing committee
          - name: Name of the publishing committee

    **Example:**

        --> {"method":"getNewsStream", "params":[0, 1]}
        <-- {"result": [{
               "id": 490,
               "title": "The new Symposium Committee!",
               "category": "web",
               "date": "2022-05-25T17:00:00+00:00",
               "author": "Donald (D.) Duck",
               "source": {
                 "id": 16,
                 "name": "Board"
               }
        }]}
    """
    if length > 250:
        length = 250

    news_items = NewsItem.objects.all()[offset:length + offset]

    result = []
    for item in news_items:
        result.append(get_basic_result(item))
    return result


@rpc_method(name='getNewsContent')
def get_news_content(news_id: int, return_type: str) -> Dict:
    """
    Returns the detailed content of a single news item from the website, including its content.

    **Module**: `news`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - news_id: The ID of the requested news item.
        - return_type: The formatting type used for the introduction and content of the item. ("html" or "markdown")

    **Return:**
      `Dict`: An array of dictionaries containing the committee information,
                                 or null if the current user has no associated person.

      Each returned element in the list has the following fields:

        - id: The identifier for this news item
        - title: The title of this item
        - category: The category of this news item
        - date: The publication date of this item (RFC3339)
        - author: The name of the person who wrote this item
        - source: A dictionary containing information about the publishing committee, including the following fields:
          - id: ID of the publishing committee
          - name: Name of the publishing committee
        - introduction: The introduction of this news item
        - content: The content of this news item

    **Raises:**

      InvalidParamsError: The `return_type` parameter was invalid.

      DoesNotExistError: The news item with this ID does not exist.

    **Example:**

        --> {"method":"getNewsContent", "params":[490, "html"]}
        <-- {"result": {
               "id": 490,
               "title": "The new Symposium Committee!",
               "category": "web",
               "date": "2022-05-25T17:00:00+00:00",
               "author": "Donald (D.) Duck",
               "source": {
                 "id": 16,
                 "name": "Board"
               },
               "introduction": "<p>Today the new Symposium Committee has been formed!</p>",
               "content": "<p><!-- html contents excluding introduction --></p>"
        }}

        --> {"method":"getNewsContent", "params":[490, "markdown"]}
        <-- {"result": {
               "id": 490,
               "title": "The new Symposium Committee!",
               "category": "web",
               "date": "2022-05-25T17:00:00+00:00",
               "author": "Donald (D.) Duck",
               "source": {
                 "id": 16,
                 "name": "Board"
               },
               "introduction": "Today the new Symposium Committee has been formed!",
               "content": "markdown _contents_ excluding introduction"
        }}
    """
    try:
        article = NewsItem.objects.get(id=news_id)
    except NewsItem.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    result = get_basic_result(article)
    add_detailed_result(article, return_type, result)
    return result


def get_basic_result(news_item):
    return {
        "id": news_item.id,
        "title": news_item.title,
        "category": 'education' if news_item.is_education_item else 'web',
        "date": news_item.publication_date.isoformat(),
        "author": news_item.author.full_name(),
        "source": {
            "id": news_item.publisher.id,
            "name": news_item.publisher.name
        }
    }


def add_detailed_result(news_item, return_type, result):
    if return_type == 'html':
        result["introduction"] = md.markdown(news_item.introduction)
        result["content"] = md.markdown(news_item.content)
    elif return_type == 'markdown':
        result["introduction"] = news_item.introduction
        result["content"] = news_item.content
    else:
        raise RPCInvalidParams("Content return type can only be of type 'html' or 'markdown'.")

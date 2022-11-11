import logging

from django.template import loader
from jsonrpc import jsonrpc_method

from amelie.api.exceptions import DoesNotExistError
from amelie.tools.templatetags import md
from amelie.news.models import NewsItem
from jsonrpc.exceptions import InvalidParamsError

logger = logging.getLogger(__name__)


@jsonrpc_method('getNewsStream(Number, Number) -> Array', validate=True)
def get_news_stream(request, offset, length):
    """Returns various types ('web', 'education') of news articles from the website"""
    news_items = NewsItem.objects.all()[offset:length + offset]

    result = []
    for item in news_items:
        result.append(get_basic_result(item))
    return result


@jsonrpc_method('getNewsContent(Number, String) -> Array', validate=True)
def get_news_content(request, id, return_type):
    """Returns the detailed content of a single news item from the website"""
    try:
        article = NewsItem.objects.get(id=id)
    except DoesNotExistError as e:
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
            "name": news_item.publisher.name,
        },
    }


def add_detailed_result(news_item, return_type, result):
    if return_type == 'html':
        result["introduction"] = md.markdown(news_item.introduction)
        result["content"] = md.markdown(news_item.content)
    elif return_type == 'markdown':
        result["introduction"] = news_item.introduction
        result["content"] = news_item.content
    else:
        raise InvalidParamsError("Content return type can only be of type 'html' or 'markdown'.")

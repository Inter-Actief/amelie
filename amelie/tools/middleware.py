from django.http import HttpResponseNotAllowed
from django.template import loader
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class HttpResponseNotAllowedMiddleware(MiddlewareMixin):
    """
    Middleware to render a template when a 405 Not Allowed error is thrown
    (e.g. with require_POST)

    Source: https://stackoverflow.com/a/4634795
    """

    # noinspection PyMethodMayBeStatic
    def process_response(self, request, response):
        if isinstance(response, HttpResponseNotAllowed):
            response.content = loader.render_to_string("405.html", request=request)
        return response


class GlobalIAVariablesMiddleware(MiddlewareMixin):
    """
    Ties handy functions to the request.
    This class is designated for passing global Inter-Actief vairables to the frontend.
    """

    # noinspection PyMethodMayBeStatic
    def process_request(self, request):
        request.book_sales_url = settings.BOOK_SALES_URL

        user = request.user
        if hasattr(user, 'person'):
            request.person = request.user.person
            request.is_board = request.user.is_superuser or request.person.is_board()
            request.is_education_committee = request.is_board or request.person.is_education_committee()

            if not request.session.get(translation.LANGUAGE_SESSION_KEY, False):
                preferred_language = request.person.preferred_language
                translation.activate(preferred_language)

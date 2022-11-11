import json
import os
from urllib.request import quote

from wsgiref.util import FileWrapper
from django.http import HttpResponse


class HttpJSONResponse(HttpResponse):
    """
    An HttpResponse of JSON content

    Unlike a Django HttpResponse, this class can accept any JSON-serializable data type as content:
    dictionaries, lists, strings, etc.

    Example::

        def some_view(request):
            return HttpJSONResponse({'foo': 'bar'})
    """

    def __init__(self, content=''):
        super(HttpJSONResponse, self).__init__(content=json.dumps(content), content_type='application/json')


class HttpResponseSendfile(HttpResponse):
    """
    HttpResponse for using X-Sendfile.

    Uses FileWrapper as a fallback if the front-end server doesn't intercept
    X-Sendfile headers.
    """

    def __init__(self, path, content_type=None, fallback=True):
        exists = os.path.exists(path)
        status = 200 if exists else 404

        # Fallback for lack of X-Sendfile support
        content = ''
        if exists and fallback:
            content = FileWrapper(open(path, 'rb'))

        # Common elements
        super(HttpResponseSendfile, self).__init__(content=content, status=status, content_type=content_type)
        self['Content-Length'] = os.path.getsize(path) if exists else 0
        filename = quote(os.path.basename(path))
        self['Content-Disposition'] = 'attachment; filename="%s"' % filename

        # X-Sendfile
        self['X-Sendfile'] = path

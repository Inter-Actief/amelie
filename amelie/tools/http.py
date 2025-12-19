import json
import os
from urllib.request import quote

from wsgiref.util import FileWrapper
from django.http import HttpResponse
from django.conf import settings


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
    HttpResponse for sending files using X-Sendfile (Apache) / X-Accel-Redirect (nginx) if available.

    Uses FileWrapper as a fallback if a proxy server is not configured.
    """

    def __init__(self, path, content_type=None):
        exists = os.path.exists(path)
        status = 200 if exists else 404

        send_method = settings.FILE_DOWNLOAD_METHOD
        if send_method not in ["nginx", "apache"]:
            send_method = None

        # Fallback for lack of X-Sendfile/X-Accel-Redirect support
        content = ''
        if exists and send_method is None:
            content = FileWrapper(open(path, 'rb'))

        # Common elements
        super(HttpResponseSendfile, self).__init__(content=content, status=status, content_type=content_type)
        self['Content-Length'] = os.path.getsize(path) if exists else 0
        filename = quote(os.path.basename(path))
        self['Content-Disposition'] = 'attachment; filename="%s"' % filename

        if send_method == "apache":
            # X-Sendfile (apache)
            self['X-Sendfile'] = path
        elif send_method == "nginx":
            # X-Accel-Redirect (nginx)
            self['X-Accel-Redirect'] = path

def get_client_ips(request):
    ips = set()
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    remote_addr = request.META.get('REMOTE_ADDR')

    # Get all IPs
    if x_forwarded_for:
        ips.update(x_forwarded_for.split(','))
    if x_real_ip:
        ips.add(x_real_ip)
    if not x_forwarded_for and not x_real_ip:
        ips.add(remote_addr)

    # Get probable real IP
    if x_real_ip:
        probable_external_ip = x_real_ip
    elif x_forwarded_for:
        probable_external_ip = x_forwarded_for[0]
    else:
        probable_external_ip = remote_addr

    return ips, probable_external_ip


def client_has_themes_disabled(request):
    all_ips, real_ip = get_client_ips(request)
    return real_ip in settings.BLOCKED_THEME_IP_RANGES

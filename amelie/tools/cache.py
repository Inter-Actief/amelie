from threading import current_thread

from django.core.cache.backends.locmem import LocMemCache
from django.utils.deprecation import MiddlewareMixin

_request_cache = {}
_installed_middleware = False


def get_request_cache():
    if not _installed_middleware:
        temp = RequestCacheMiddleware()
        temp.process_request(None)

    return _request_cache[current_thread()]


# LocMemCache is a threadsafe local memory cache
class RequestCache(LocMemCache):
    def __init__(self):
        name = 'locmemcache@%i' % hash(current_thread())
        params = dict()
        super(RequestCache, self).__init__(name, params)


class RequestCacheMiddleware(MiddlewareMixin):
    def __init__(self, *args, **kwargs):
        global _installed_middleware
        _installed_middleware = True
        super(RequestCacheMiddleware, self).__init__(*args, **kwargs)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def process_request(self, request):
        cache = _request_cache.get(current_thread()) or RequestCache()
        _request_cache[current_thread()] = cache

        cache.clear()

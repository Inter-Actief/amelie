from django.conf import settings

from amelie.tools.buildinfo import get_build_info, get_host_info


# noinspection PyUnusedLocal
def environment(request):
    """ Template context processor to add debug and env variables to template context. """
    return {
        'debug': settings.DEBUG,
        'env': settings.ENV,
        'build_info': get_build_info(),
        'host_info': get_host_info(),
    }

from django.conf import settings


# noinspection PyUnusedLocal
def environment(request):
    """ Template context processor to add debug and env variables to template context. """
    return {
        'debug': settings.DEBUG,
        'env': settings.ENV
    }

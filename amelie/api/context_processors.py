from django.conf import settings


def absolute_path_to_site(context):
    return {'ABSOLUTE_PATH_TO_SITE': settings.ABSOLUTE_PATH_TO_SITE}

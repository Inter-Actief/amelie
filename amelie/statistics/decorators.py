from datetime import date

from django.db import transaction

from amelie.statistics.models import Hits


def track_hits(page):
    if len(page) > 255:
        raise ValueError("The name of a page must be smaller than 256 characters")

    def transform_method(method):
        def new_method(request, *args, **kwargs):
            with transaction.atomic():
                today = date.today()
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
                hits, _ = Hits.objects.get_or_create(date_start=today,
                                                     page=page,
                                                     user_agent=user_agent,
                                                     defaults={"date_end": today})
                hits.hit_count += 1
                hits.save()

            return method(request, *args, **kwargs)

        return new_method

    return transform_method

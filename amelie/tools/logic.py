from django.utils import timezone

from amelie.tools.cache import get_request_cache


# Handy functions
def current_academic_year_strict():
    """
    Calculate the current academic year, beginning on 1 september.
    """
    today = timezone.now()
    if today.month >= 9:
        return today.year
    else:
        return today.year - 1


def current_academic_year_with_holidays():
    """
    Calculate the current academic year, taking into account the holidays.

    This counts the summer holidays as a part of the new academic year.
    """

    cache = get_request_cache()
    result = cache.get('current_academic_year_with_holidays', None)

    # It's unnecessary to calculate the current academic year every single time.
    # Save the result in a cache for the current request.
    if result is None:
        from amelie.education.models import Period

        today = timezone.now()

        if today.month >= 9 or Period.objects.filter(year=today.year - 1, start__lte=today, end__gte=today) \
                .count() == 0:  # Summer holidays
            result = today.year
        else:
            result = today.year - 1

        cache.set('current_academic_year_with_holidays', result)

    # Done
    return result


def association_year(dt=None):
    """
    Calculate the association year starting on 1 july.

    If a datetime object is given, the association year belonging to that date is calculated.
    """

    if dt is None:
        dt = timezone.now()

    if dt.month >= 7:
        return dt.year
    else:
        return dt.year - 1


current_association_year = association_year

from django.utils import timezone

from amelie.tools.cache import get_request_cache


# Handy functions
def current_academic_year_strict(dt=None):
    """
    Calculate the current academic year, beginning on 1 September.

    If a datetime object is given, the association year belonging to that date is calculated.
    """
    if dt is None:
        dt = timezone.now()

    if dt.month >= 9:
        return dt.year
    else:
        return dt.year - 1


def current_academic_year_with_holidays(dt=None):
    """
    Calculate the current academic year, taking into account the holidays.

    This counts the summer holidays as a part of the new academic year.

    If a datetime object is given, the association year belonging to that date is calculated.
    """

    cache = get_request_cache()
    result = cache.get('current_academic_year_with_holidays', None)

    # It's unnecessary to calculate the current academic year every single time.
    # Save the result in a cache for the current request.
    if result is None:
        from amelie.education.models import Period

        if dt is None:
            dt = timezone.now()

        if dt.month >= 9 or Period.objects.filter(year=dt.year - 1, start__lte=dt, end__gte=dt) \
                .count() == 0:  # Summer holidays
            result = dt.year
        else:
            result = dt.year - 1

        cache.set('current_academic_year_with_holidays', result)

    # Done
    return result


def association_year(dt=None):
    """
    Calculate the association year starting on 1 July.

    If a datetime object is given, the association year belonging to that date is calculated.
    """

    if dt is None:
        dt = timezone.now()

    if dt.month >= 7:
        return dt.year
    else:
        return dt.year - 1


current_association_year = association_year

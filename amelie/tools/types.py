def get_int(haystack, needle, default=0, min_value=None, max_value=None):
    # Get integer
    try:
        value = int(haystack.get(needle, default))
    except ValueError:
        value = default

    # Check range
    if min_value is not None:
        value = max(min_value, value)

    if max_value is not None:
        value = min(max_value, value)

    # Done
    return value

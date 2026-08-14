import locale
import threading
from contextlib import contextmanager


LOCALE_LOCK = threading.Lock()


@contextmanager
def setlocale(name):
    """
    A Contextmanager to change the locale within the context to the given locale string.
    This allows tools like strptime to parse time strings in other locales than the system locale.
    e.g. "with setlocale('en_US'): ..."
    """
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)

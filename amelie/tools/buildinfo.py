import os
import socket
from functools import lru_cache

from django.conf import settings


def get_build_file_contents(filename) -> str:
    if filename not in ["BUILD_BRANCH", "BUILD_COMMIT", "BUILD_DATE"]:
        return "denied"
    path = os.path.join(settings.BASE_PATH, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"
    except OSError:
        return "error"


@lru_cache(maxsize=1)
def get_build_branch():
    return get_build_file_contents("BUILD_BRANCH")


@lru_cache(maxsize=1)
def get_build_commit():
    return get_build_file_contents("BUILD_COMMIT")


@lru_cache(maxsize=1)
def get_build_date():
    return get_build_file_contents("BUILD_DATE")


@lru_cache(maxsize=1)
def get_build_info():
    return {
        "branch": get_build_branch(),
        "commit": get_build_commit(),
        "date": get_build_date()
    }

@lru_cache(maxsize=1)
def get_host_info():
    return {
        "host": socket.gethostname(),
        "pid": os.getpid()
    }

from corsheaders.signals import check_request_enabled


def check_cors_access(sender, request, **kwargs):
    """
    Check CORS access rules for this request. Return True if the CORS request is allowed, False if it is not allowed.
    Used as a signal handler for the `check_request_enabled` signal from the `corsheaders` library.
    Note that the regular CORS checks in the settings also still apply, so CORS_ALLOWED_ORIGINS is also still honoured.

    The current rules this handler is checking are as follows:
    - CORS requests to `/api/` and `/graphql/` are always allowed, regardless of origin.
    - Otherwise, the request is denied.
    """
    return request.path.startswith("/api/") or request.path.startswith("/graphql/")

check_request_enabled.connect(check_cors_access)

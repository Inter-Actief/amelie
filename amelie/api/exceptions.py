from jsonrpc.exceptions import Error


class UnknownDeviceError(Error):
    """ The DeviceId was not recognized. """
    code = 406
    message = 'Your DeviceId is not known.'


class NotLoggedInError(Error):
    """ The token was not recognized. """
    code = 403
    message = 'You are not logged in.'


class TokenExpiredError(NotLoggedInError):
    """ The token that was provided is expired """
    code = 403
    message = 'The token you provided was either expired or revoked.'


class PermissionDeniedError(Error):
    """ The token that was provided is expired """
    code = 404
    message = 'You are not permitted to view this item.'


class DoesNotExistError(Error):
    status = 404
    code = 404
    message = 'The requested object does not exist.'


class SignupError(Error):
    """ Tried subscribing to event without all required options. """
    code = 412


class MissingOptionError(SignupError):
    """ Tried subscribing to event without all required options. """
    message = 'You need to answer all required options.'

from modernrpc.exceptions import RPCException, RPC_INVALID_PARAMS, RPC_CUSTOM_ERROR_BASE


class UnknownDeviceError(RPCException):
    """ The DeviceId was not recognized. """
    def __init__(self):
        super(UnknownDeviceError, self).__init__(
            code=(RPC_CUSTOM_ERROR_BASE + 6),
            message='Your DeviceId is not known.'
        )


class NotLoggedInError(RPCException):
    """ The token was not recognized. """
    def __init__(self, message=None):
        super(NotLoggedInError, self).__init__(
            code=(RPC_CUSTOM_ERROR_BASE + 3),
            message='You are not logged in.' if message is None else message
        )


class TokenExpiredError(NotLoggedInError):
    """ The token that was provided is expired """
    def __init__(self):
        super(TokenExpiredError, self).__init__(
            message='The token you provided was either expired or revoked.'
        )


class PermissionDeniedError(RPCException):
    """ The token that was provided is expired """
    def __init__(self):
        super(PermissionDeniedError, self).__init__(
            code=(RPC_CUSTOM_ERROR_BASE + 4),
            message='You are not permitted to view this item.'
        )


class DoesNotExistError(RPCException):
    def __init__(self, message=None):
        super(DoesNotExistError, self).__init__(
            code=(RPC_CUSTOM_ERROR_BASE + 4),
            message='The requested object does not exist.' if message is None else message
        )


class SignupError(RPCException):
    """ Tried subscribing to event without all required options. """
    def __init__(self, message):
        super(SignupError, self).__init__(
            code=RPC_INVALID_PARAMS,
            message=message
        )


class MissingOptionError(SignupError):
    """ Tried subscribing to event without all required options. """
    def __init__(self):
        super(MissingOptionError, self).__init__(
            message='You need to answer all required options.'
        )

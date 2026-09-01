"""Exceptions used by the IDM integration."""


class IDMException(Exception):
    """Base class for all exceptions raised by IDM."""


class IDMServiceException(IDMException):
    """Raised when the IDM service is unavailable or misbehaves."""


class BadCredentialsException(IDMException):
    """Raised when the supplied credentials are rejected."""


class NotAuthenticatedException(IDMException):
    """Raised when the session is no longer valid."""


class GatewayTimeoutException(IDMServiceException):
    """Raised when the server times out."""


class BadGatewayException(IDMServiceException):
    """Raised when the server returns a Bad Gateway."""

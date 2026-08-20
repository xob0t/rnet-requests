"""
wrequests.exceptions
~~~~~~~~~~~~~~~~~~~~~~~~

This module contains the exceptions used in wrequests,
designed to be compatible with the requests library.
"""

from typing import Any

import wreq.exceptions as wreq_exc


class RequestException(IOError):
    """There was an ambiguous exception that occurred while handling your request."""

    def __init__(
        self,
        *args: Any,
        response: Any | None = None,
        request: Any | None = None,
    ):
        self.response = response
        self.request = request
        super().__init__(*args)


class InvalidJSONError(RequestException):
    """A JSON error occurred."""

    pass


class JSONDecodeError(InvalidJSONError):
    """Couldn't decode the text into json."""

    def __init__(self, *args: Any, doc: str = "", pos: int = 0, **kwargs: Any):
        self.doc = doc
        self.pos = pos
        super().__init__(*args, **kwargs)


class HTTPError(RequestException):
    """An HTTP error occurred."""

    pass


class ConnectionError(RequestException):
    """A Connection error occurred."""

    pass


class ProxyError(ConnectionError):
    """A proxy error occurred."""

    pass


class SSLError(ConnectionError):
    """An SSL error occurred."""

    pass


class Timeout(RequestException):
    """The request timed out.

    Catching this error will catch both
    :exc:`~requests.exceptions.ConnectTimeout` and
    :exc:`~requests.exceptions.ReadTimeout` errors.
    """

    pass


class ConnectTimeout(ConnectionError, Timeout):
    """The request timed out while trying to connect to the remote server.

    Requests that produced this error are safe to retry.
    """

    pass


class ReadTimeout(Timeout):
    """The server did not send any data in the allotted amount of time."""

    pass


class URLRequired(RequestException):
    """A valid URL is required to make a request."""

    pass


class TooManyRedirects(RequestException):
    """Too many redirects."""

    pass


class SessionClosed(RequestException):
    """The session has already been closed."""

    pass


class MissingSchema(RequestException, ValueError):
    """The URL scheme (e.g. http or https) is missing."""

    pass


class InvalidSchema(RequestException, ValueError):
    """The URL scheme provided is either invalid or unsupported."""

    pass


class InvalidURL(RequestException, ValueError):
    """The URL provided was invalid."""

    pass


class InvalidHeader(RequestException, ValueError):
    """The header value provided was invalid."""

    pass


class InvalidProxyURL(InvalidURL):
    """The proxy URL provided was invalid."""

    pass


class ChunkedEncodingError(RequestException):
    """The server declared chunked encoding but sent an invalid chunk."""

    pass


class ContentDecodingError(RequestException):
    """Failed to decode response content."""

    pass


class StreamConsumedError(RequestException, TypeError):
    """The content for this response was already consumed."""

    pass


class RetryError(RequestException):
    """Custom retries logic failed."""

    pass


class UnrewindableBodyError(RequestException):
    """Requests encountered an error when trying to rewind a body."""

    pass


# Warnings
class RequestsWarning(UserWarning):
    """Base warning for requests."""

    pass


class FileModeWarning(RequestsWarning, DeprecationWarning):
    """A file was opened in text mode, but Requests determined its binary length."""

    pass


class RequestsDependencyWarning(RequestsWarning):
    """An imported dependency doesn't match the expected version range."""

    pass


def convert_wreq_exception(exc: Exception) -> RequestException:
    """Convert a wreq exception to a requests-compatible exception.

    wreq exceptions:
    - TimeoutError: request timed out
    - ConnectionError: connection failed
    - ConnectionResetError: connection was reset
    - RedirectError: too many redirects
    - DecodingError: failed to decode response
    - ProxyConnectionError: proxy connection failed
    - TlsError: TLS/SSL error
    - RequestError: generic request error
    - BuilderError: error building request
    - StatusError: HTTP status error
    - BodyError: error reading body
    - UpgradeError: websocket upgrade error
    - WebSocketError: websocket error
    """
    if isinstance(exc, wreq_exc.TimeoutError):
        return Timeout(str(exc))
    elif isinstance(exc, wreq_exc.ConnectionResetError):
        return ConnectionError(str(exc))
    elif isinstance(exc, wreq_exc.ProxyConnectionError):
        return ProxyError(str(exc))
    elif isinstance(exc, wreq_exc.ConnectionError):
        return ConnectionError(str(exc))
    elif isinstance(exc, wreq_exc.RedirectError):
        return TooManyRedirects(str(exc))
    elif isinstance(exc, wreq_exc.TlsError):
        return SSLError(str(exc))
    elif isinstance(exc, (wreq_exc.DecodingError, wreq_exc.BodyError)):
        return ContentDecodingError(str(exc))
    elif isinstance(exc, wreq_exc.StatusError):
        return HTTPError(str(exc))
    elif isinstance(exc, (wreq_exc.RequestError, wreq_exc.BuilderError)):
        return RequestException(str(exc))
    elif isinstance(exc, (wreq_exc.UpgradeError, wreq_exc.WebSocketError)):
        return ConnectionError(str(exc))
    else:
        return RequestException(str(exc))

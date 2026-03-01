"""
rnet_requests.models
~~~~~~~~~~~~~~~~~~~~

This module contains the primary objects that power rnet-requests.
"""

from __future__ import annotations

import json as _json
from collections.abc import Iterator
from typing import (
    TYPE_CHECKING,
    Any,
)
from urllib.parse import parse_qsl, urlencode, urlparse

from .cookies import Cookies
from .exceptions import (
    HTTPError,
    JSONDecodeError,
)
from .structures import CaseInsensitiveDict

if TYPE_CHECKING:
    from rnet import Response as RnetResponse
    from rnet.blocking import BlockingResponse as RnetBlockingResponse


class Request:
    """A user-created :class:`Request <Request>` object.

    Used to prepare a :class:`PreparedRequest <PreparedRequest>`, which is sent
    to the server.

    :param method: HTTP method to use.
    :param url: URL to send.
    :param headers: dictionary of headers to send.
    :param files: dictionary of {filename: fileobject} files to multipart upload.
    :param data: the body to attach to the request. If a dictionary or
        list of tuples ``[(key, value)]`` is provided, form-encoding will
        take place.
    :param json: json for the body to attach to the request.
    :param params: URL parameters to append to the URL. If a dictionary or
        list of tuples ``[(key, value)]`` is provided, URL-encoding will take place.
    :param auth: Auth handler or (user, pass) tuple.
    :param cookies: dictionary or CookieJar of cookies to attach to this request.

    Usage::

      >>> import rnet_requests as requests
      >>> req = requests.Request('GET', 'https://httpbin.org/get')
      >>> req.prepare()
      <PreparedRequest [GET]>
    """

    def __init__(
        self,
        method: str | None = None,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        files: Any | None = None,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None = None,
        json: Any | None = None,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        auth: tuple[str, str] | str | None = None,
        cookies: dict[str, str] | None = None,
    ):
        # Default empty dict for headers
        if headers is None:
            headers = {}
        if params is None:
            params = {}
        if cookies is None:
            cookies = {}

        self.method = method
        self.url = url
        self.headers = headers
        self.files = files
        self.data = data
        self.json = json
        self.params = params
        self.auth = auth
        self.cookies = cookies

    def __repr__(self) -> str:
        return f"<Request [{self.method}]>"

    def prepare(self) -> PreparedRequest:
        """Constructs a PreparedRequest for transmission and returns it."""
        p = PreparedRequest()
        p.prepare(
            method=self.method,
            url=self.url,
            headers=self.headers,
            files=self.files,
            data=self.data,
            json=self.json,
            params=self.params,
            auth=self.auth,
            cookies=self.cookies,
        )
        return p


class PreparedRequest:
    """The fully mutable :class:`PreparedRequest <PreparedRequest>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually.

    Usage::

      >>> import rnet_requests as requests
      >>> req = requests.Request('GET', 'https://httpbin.org/get')
      >>> r = req.prepare()
      >>> r
      <PreparedRequest [GET]>

      >>> s = requests.Session()
      >>> s.send(r)
      <Response [200]>
    """

    def __init__(self) -> None:
        self.method: str | None = None
        self.url: str | None = None
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict()
        self.body: str | bytes | None = None
        self._cookies: dict[str, str] = {}

    def __repr__(self) -> str:
        return f"<PreparedRequest [{self.method}]>"

    def prepare(
        self,
        method: str | None = None,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        files: Any | None = None,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None = None,
        json: Any | None = None,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        auth: tuple[str, str] | str | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        """Prepares the entire request with the given parameters."""
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files, json)
        self.prepare_auth(auth)

    def prepare_method(self, method: str | None) -> None:
        """Prepares the given HTTP method."""
        self.method = method
        if self.method:
            self.method = self.method.upper()

    def prepare_url(
        self,
        url: str | None,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
    ) -> None:
        """Prepares the given HTTP URL."""
        if url is None:
            self.url = None
            return

        # Handle params
        if params:
            if isinstance(params, dict):
                params_list = list(params.items())
            else:
                params_list = list(params)

            parsed = urlparse(url)
            existing_params = parse_qsl(parsed.query)
            all_params = existing_params + params_list
            new_query = urlencode(all_params)

            self.url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if new_query:
                self.url += f"?{new_query}"
            if parsed.fragment:
                self.url += f"#{parsed.fragment}"
        else:
            self.url = url

    def prepare_headers(self, headers: dict[str, str] | None) -> None:
        """Prepares the given HTTP headers."""
        self.headers = CaseInsensitiveDict(headers or {})

    def prepare_cookies(self, cookies: dict[str, str] | None) -> None:
        """Prepares the given HTTP cookies."""
        self._cookies = cookies or {}

    def prepare_body(
        self,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None = None,
        files: Any | None = None,
        json: Any | None = None,
    ) -> None:
        """Prepares the given HTTP body data."""
        if json is not None:
            self.headers["Content-Type"] = "application/json"
            self.body = _json.dumps(json)
        elif data is not None:
            if isinstance(data, (str, bytes)):
                self.body = data
            elif isinstance(data, (dict, list)):
                self.headers["Content-Type"] = "application/x-www-form-urlencoded"
                self.body = urlencode(data)
        # TODO: Handle files/multipart

    def prepare_auth(self, auth: tuple[str, str] | str | None = None) -> None:
        """Prepares the given HTTP auth data."""
        # Auth will be handled at request time
        self._auth = auth

    @property
    def path_url(self) -> str:
        """Build the path URL to use."""
        if self.url:
            parsed = urlparse(self.url)
            path = parsed.path or "/"
            if parsed.query:
                path += f"?{parsed.query}"
            return path
        return "/"


class Response:
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    This class wraps rnet's Response to provide a requests-compatible interface.
    """

    def __init__(self) -> None:
        self._content: bytes | None = None
        self._text: str | None = None
        self._json: Any | None = None
        self._content_consumed: bool = False

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code: int = 0

        #: Case-insensitive Dictionary of Response Headers.
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict()

        #: File-like object representation of response (for advanced usage).
        self.raw: Any | None = None

        #: Final URL location of Response.
        self.url: str = ""

        #: Encoding to decode with when accessing r.text.
        self.encoding: str | None = None

        #: Default encoding for decoding response content.
        self.default_encoding: str | Any = "utf-8"

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request. Any redirect responses will end
        #: up here.
        self.history: list[Response] = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason: str = ""

        #: A CookieJar of Cookies the server sent back.
        #: Uses Cookies class for curl_cffi compatibility.
        self.cookies: Cookies = Cookies()

        #: The amount of time elapsed between sending the request
        #: and the arrival of the response (as a timedelta).
        self.elapsed: Any | None = None

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request: PreparedRequest | None = None

        # Internal: rnet response object
        self._rnet_response: Any | None = None

    def __repr__(self) -> str:
        return f"<Response [{self.status_code}]>"

    def __bool__(self) -> bool:
        """Returns True if :attr:`status_code` is less than 400.

        This attribute checks if the status code of the response is between
        400 and 600 to see if there was a client error or a server error. If
        the status code is between 200 and 400, this will return True.
        """
        return self.ok

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __iter__(self) -> Iterator[bytes]:
        """Allows you to iterate over the response content."""
        return self.iter_content(128)

    @property
    def ok(self) -> bool:
        """Returns True if :attr:`status_code` is less than 400, False otherwise."""
        try:
            self.raise_for_status()
        except HTTPError:
            return False
        return True

    @property
    def is_redirect(self) -> bool:
        """True if this Response is a well-formed HTTP redirect that could have
        been processed automatically (by :meth:`Session.resolve_redirects`).
        """
        return "location" in self.headers and self.status_code in (
            301,
            302,
            303,
            307,
            308,
        )

    @property
    def is_permanent_redirect(self) -> bool:
        """True if this Response is a permanent redirect."""
        return "location" in self.headers and self.status_code in (301, 308)

    @property
    def apparent_encoding(self) -> str:
        """The apparent encoding, provided by the charset_normalizer library."""
        # Simple fallback - in production you'd use charset_normalizer
        return self.encoding or "utf-8"

    @property
    def content(self) -> bytes:
        """Content of the response, in bytes."""
        if self._content is None:
            self._content = b""
        return self._content

    @content.setter
    def content(self, value: bytes) -> None:
        self._content = value
        self._content_consumed = True

    @property
    def text(self) -> str:
        """Content of the response, in unicode.

        If Response.encoding is None, encoding will be guessed using
        ``charset_normalizer``.

        The encoding of the response content is determined based solely on HTTP
        headers, following RFC 2616 to the letter. If you can take advantage of
        non-HTTP knowledge to make a better guess at the encoding, you should
        set ``r.encoding`` appropriately before accessing this property.
        """
        if self._text is not None:
            return self._text

        # Decode content
        encoding = self.encoding
        if encoding is None:
            encoding = self.apparent_encoding

        try:
            self._text = self.content.decode(encoding, errors="replace")
        except (LookupError, TypeError):
            self._text = self.content.decode("utf-8", errors="replace")

        return self._text

    def json(self, **kwargs: Any) -> Any:
        """Returns the json-encoded content of a response, if any.

        :param \\*\\*kwargs: Optional arguments that ``json.loads`` takes.
        :raises JSONDecodeError: If the response body does not contain valid json.
        """
        if self._json is not None:
            return self._json

        try:
            self._json = _json.loads(self.text, **kwargs)
        except ValueError as e:
            raise JSONDecodeError(str(e), doc=self.text, pos=0) from e

        return self._json

    def raise_for_status(self) -> None:
        """Raises :class:`HTTPError`, if one occurred.

        :raises HTTPError: If the response status code indicates an error.
        """
        http_error_msg = ""

        if 400 <= self.status_code < 500:
            http_error_msg = (
                f"{self.status_code} Client Error: {self.reason} for url: {self.url}"
            )
        elif 500 <= self.status_code < 600:
            http_error_msg = (
                f"{self.status_code} Server Error: {self.reason} for url: {self.url}"
            )

        if http_error_msg:
            raise HTTPError(http_error_msg, response=self)

    def iter_content(
        self, chunk_size: int = 1, decode_unicode: bool = False
    ) -> Iterator[bytes]:
        """Iterates over the response data.

        When stream=True is set on the request, this avoids reading the
        content at once into memory for large responses.

        :param chunk_size: Number of bytes to read at a time.
        :param decode_unicode: If True, content will be decoded using the best
            available encoding based on the response.
        """
        content = self.content
        for i in range(0, len(content), chunk_size):
            chunk = content[i : i + chunk_size]
            if decode_unicode:
                yield chunk.decode(self.encoding or "utf-8", errors="replace").encode()
            else:
                yield chunk

    def iter_lines(
        self,
        chunk_size: int = 512,
        decode_unicode: bool = False,
        delimiter: str | bytes | None = None,
    ) -> Iterator[bytes]:
        """Iterates over the response data, one line at a time.

        When stream=True is set on the request, this avoids reading the
        content at once into memory for large responses.

        :param chunk_size: Number of bytes to read at a time.
        :param decode_unicode: If True, content will be decoded using the best
            available encoding based on the response.
        :param delimiter: The line delimiter.
        """
        pending = b""

        if delimiter is None:
            delimiter = b"\n"
        elif isinstance(delimiter, str):
            delimiter = delimiter.encode()

        for chunk in self.iter_content(
            chunk_size=chunk_size, decode_unicode=decode_unicode
        ):
            pending += chunk
            lines = pending.split(delimiter)

            yield from lines[:-1]

            pending = lines[-1]

        if pending:
            yield pending

    def close(self) -> None:
        """Releases the connection back to the pool."""
        # rnet handles connection pooling internally
        pass

    @classmethod
    def from_rnet_response(
        cls,
        rnet_resp: RnetResponse | RnetBlockingResponse,
        content: bytes,
        text: str | None = None,
    ) -> Response:
        """Create a Response from an rnet response object.

        Note: This method is updated for rnet v3 API compatibility.
        """
        response = cls()
        response._rnet_response = rnet_resp
        response._content = content
        response._text = text
        response._content_consumed = True

        # rnet v3: status is a StatusCode object, use .as_int()
        response.status_code = rnet_resp.status.as_int()
        response.url = rnet_resp.url
        response.encoding = (
            rnet_resp.encoding if hasattr(rnet_resp, "encoding") else None
        )

        # Convert headers (rnet v3: HeaderMap uses keys()/get())
        response.headers = CaseInsensitiveDict()
        for key in rnet_resp.headers.keys():  # noqa: SIM118
            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            value = rnet_resp.headers.get(key_str)
            if value is not None:
                value_str = (
                    value.decode("utf-8") if isinstance(value, bytes) else str(value)
                )
                response.headers[key_str] = value_str

        # Convert cookies - use Cookies class for curl_cffi compatibility
        response.cookies = Cookies()
        for cookie in rnet_resp.cookies:
            response.cookies.set(cookie.name, cookie.value)

        # Set reason from status code
        response.reason = _get_reason_phrase(response.status_code)

        return response


def _get_reason_phrase(status_code: int) -> str:
    """Get the HTTP reason phrase for a status code."""
    reasons = {
        100: "Continue",
        101: "Switching Protocols",
        200: "OK",
        201: "Created",
        202: "Accepted",
        203: "Non-Authoritative Information",
        204: "No Content",
        205: "Reset Content",
        206: "Partial Content",
        300: "Multiple Choices",
        301: "Moved Permanently",
        302: "Found",
        303: "See Other",
        304: "Not Modified",
        305: "Use Proxy",
        307: "Temporary Redirect",
        308: "Permanent Redirect",
        400: "Bad Request",
        401: "Unauthorized",
        402: "Payment Required",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        407: "Proxy Authentication Required",
        408: "Request Timeout",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        412: "Precondition Failed",
        413: "Payload Too Large",
        414: "URI Too Long",
        415: "Unsupported Media Type",
        416: "Range Not Satisfiable",
        417: "Expectation Failed",
        418: "I'm a Teapot",
        421: "Misdirected Request",
        422: "Unprocessable Entity",
        423: "Locked",
        424: "Failed Dependency",
        425: "Too Early",
        426: "Upgrade Required",
        428: "Precondition Required",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        451: "Unavailable For Legal Reasons",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
        505: "HTTP Version Not Supported",
        506: "Variant Also Negotiates",
        507: "Insufficient Storage",
        508: "Loop Detected",
        510: "Not Extended",
        511: "Network Authentication Required",
    }
    return reasons.get(status_code, "Unknown")

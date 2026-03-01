"""
rnet_requests.sessions
~~~~~~~~~~~~~~~~~~~~~~

This module provides a Session object that manages settings across requests,
providing a familiar requests-like interface while using rnet as the backend.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
)

from rnet import Proxy, Version
from rnet.blocking import Client as BlockingClient

from .base import (
    DEFAULT_MAX_REDIRECTS,
    HttpVersionLiteral,
    RetryStrategy,
    SessionBase,
)
from .base import (
    is_absolute_url as _is_absolute_url,
)
from .base import (
    normalize_retry as _normalize_retry,
)
from .exceptions import (
    HTTPError,
    convert_rnet_exception,
)
from .impersonate import (
    Emulation,
    EmulationOption,
    EmulationOS,
)
from .models import PreparedRequest, Response

if TYPE_CHECKING:
    from .multipart import Multipart


class Session(SessionBase):
    """A requests-compatible Session class backed by rnet.

    Provides cookie persistence, connection-pooling, and configuration.

    Basic Usage::

      >>> import rnet_requests as requests
      >>> s = requests.Session()
      >>> s.get('https://httpbin.org/get')
      <Response [200]>

    With browser impersonation::

      >>> s = requests.Session(impersonate='chrome')
      >>> s.get('https://tls.peet.ws/api/all')
      <Response [200]>

    Or with a custom rnet Client::

      >>> from rnet.blocking import Client
      >>> from rnet import Emulation
      >>> client = Client(emulation=Emulation.Firefox139)
      >>> s = requests.Session(client=client)
    """

    _client: BlockingClient

    def __init__(
        self,
        impersonate: str | Emulation | EmulationOption | None = None,
        impersonate_os: str | EmulationOS | None = None,
        client: BlockingClient | None = None,
        # Client options
        timeout: float | tuple[float, float] | None = None,
        verify: bool | None = None,
        proxies: str | dict[str, str] | list[Proxy] | None = None,
        proxy: str | None = None,
        proxy_auth: tuple[str, str] | None = None,
        allow_redirects: bool = True,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        # curl_cffi compatible options
        base_url: str | None = None,
        params: dict[str, str] | None = None,
        retry: int | RetryStrategy | None = None,
        # Additional rnet options
        user_agent: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        # Advanced options
        http_version: Version | HttpVersionLiteral | None = None,
        default_headers: bool = True,
        default_encoding: str | Callable[[bytes], str] = "utf-8",
        interface: str | None = None,
        cert: str | tuple[str, str] | None = None,
        debug: bool = False,
        discard_cookies: bool = False,
        raise_for_status: bool = False,
        **kwargs: Any,
    ):
        """Initialize a Session.

        :param impersonate: Browser to impersonate. Can be a string like 'chrome',
            'firefox', 'safari', or an rnet Emulation enum value.
        :param impersonate_os: OS to impersonate. Can be 'windows', 'macos',
            'linux', 'android', 'ios', or an rnet EmulationOS enum value.
        :param client: An existing rnet blocking Client to use.
        :param timeout: Default timeout for requests in seconds, or tuple of
            (connect_timeout, read_timeout).
        :param verify: Whether to verify SSL certificates.
        :param proxies: Proxy configuration. Can be a URL string, dict,
            or list of Proxy.
        :param proxy: Single proxy URL (alternative to proxies).
        :param proxy_auth: HTTP basic auth for proxy, a tuple of (username, password).
        :param allow_redirects: Whether to follow redirects.
        :param max_redirects: Maximum number of redirects to follow.
        :param base_url: Base URL for relative URLs in requests.
        :param params: Default query parameters to add to every request.
        :param retry: Number of retries or RetryStrategy for failed requests.
        :param user_agent: Custom User-Agent string.
        :param headers: Default headers to send with every request.
        :param cookies: Initial cookies.
        :param auth: HTTP basic auth, a tuple of (username, password).
        :param http_version: HTTP version to use. Can be "HTTP/1.0", "HTTP/1.1",
            "HTTP/2", "HTTP/3", or a Version enum value.
        :param default_headers: Whether to use default browser headers (default True).
        :param default_encoding: Default encoding for response content.
            Defaults to "utf-8". Can be a callable that returns the encoding.
        :param interface: Network interface to use.
        :param cert: Client certificate. Can be a path to a PEM file or tuple of
            (cert_path, key_path) for PKCS#8 format.
        :param debug: Enable debug mode for the client.
        :param discard_cookies: If True, don't store cookies from responses.
        :param raise_for_status: Automatically raise HTTPError for 4xx/5xx responses.
        """
        # Create or use provided client
        if client is not None:
            # When using an existing client, still initialize session state
            self._closed = False
            self._timeout = timeout
            self._verify = verify if verify is not None else True
            self._allow_redirects = allow_redirects
            self._max_redirects = max_redirects
            self.retry = _normalize_retry(retry)
            self.default_encoding = default_encoding
            self.discard_cookies = discard_cookies
            self.raise_for_status = raise_for_status
            if base_url and not _is_absolute_url(base_url):
                raise ValueError("You need to provide an absolute url for 'base_url'")
            self.base_url = base_url
            self.params = params or {}
            from .cookies import Cookies
            from .structures import CaseInsensitiveDict

            self.headers = CaseInsensitiveDict(headers or {})
            self.cookies = Cookies(cookies)
            self.auth = auth
            self.proxy_auth = proxy_auth
            self._client = client
        else:
            # Use base class initialization
            client_kwargs = self._init_session(
                impersonate=impersonate,
                impersonate_os=impersonate_os,
                timeout=timeout,
                verify=verify,
                proxies=proxies,
                proxy=proxy,
                proxy_auth=proxy_auth,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                base_url=base_url,
                params=params,
                retry=retry,
                user_agent=user_agent,
                headers=headers,
                cookies=cookies,
                auth=auth,
                http_version=http_version,
                default_headers=default_headers,
                default_encoding=default_encoding,
                interface=interface,
                cert=cert,
                debug=debug,
                discard_cookies=discard_cookies,
                raise_for_status=raise_for_status,
                extra_kwargs=kwargs,
            )
            # Create the rnet client
            self._client = BlockingClient(**client_kwargs)

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Closes all adapters and as such the session."""
        self._closed = True

    def request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        auth: tuple[str, str] | str | None = None,
        timeout: float | int | tuple[float, float] | None = None,
        allow_redirects: bool | None = None,
        proxies: str | dict[str, str] | None = None,
        proxy_auth: tuple[str, str] | None = None,
        verify: bool | None = None,
        stream: bool = False,
        cert: Any | None = None,
        json: Any | None = None,
        multipart: Multipart | None = None,
        referer: str | None = None,
        default_encoding: str | Callable[[bytes], str] | None = None,
        discard_cookies: bool | None = None,
    ) -> Response:
        """Constructs a :class:`Request <Request>`, prepares it and sends it.

        :param method: method for the new :class:`Request` object.
        :param url: URL for the new :class:`Request` object.
        :param params: (optional) Dictionary or bytes to be sent in the query
            string for the :class:`Request`.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) json to send in the body of the :class:`Request`.
        :param headers: (optional) Dictionary of HTTP Headers to send with the
            :class:`Request`.
        :param cookies: (optional) Dict or CookieJar object to send with the
            :class:`Request`.
        :param files: (optional) Dictionary or list of tuples ``(filename, fileobj)``
            to upload.
        :param auth: (optional) Auth tuple or string to enable Basic/Digest/Custom
            HTTP Auth.
        :param timeout: (optional) How long to wait for the server to send data
            before giving up, as a float, or a :ref:`(connect timeout, read
            timeout) <timeouts>` tuple.
        :param allow_redirects: (optional) Set to True by default.
        :param proxies: (optional) Dictionary mapping protocol to the URL of
            the proxy.
        :param proxy_auth: (optional) HTTP basic auth for proxy.
        :param verify: (optional) Whether to verify SSL certificates.
        :param stream: (optional) Whether to immediately download the response
            content.
        :param cert: (optional) SSL client certificate.
        :param multipart: (optional) Multipart form data to send.
        :param referer: (optional) Shortcut for setting Referer header.
        :param default_encoding: (optional) Override session default encoding.
        :param discard_cookies: (optional) Don't store cookies from this response.
        :rtype: requests.Response
        """
        # Use retry logic
        strategy = self.retry
        last_exception: Exception | None = None

        for attempt in range(strategy.count + 1):
            try:
                return self._request_once(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                    cookies=cookies,
                    files=files,
                    auth=auth,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    proxies=proxies,
                    proxy_auth=proxy_auth,
                    verify=verify,
                    stream=stream,
                    cert=cert,
                    json=json,
                    multipart=multipart,
                    referer=referer,
                    default_encoding=default_encoding,
                    discard_cookies=discard_cookies,
                )
            except Exception as e:
                last_exception = e
                if attempt == strategy.count:
                    raise
                delay = self._retry_delay(attempt + 1)
                if delay:
                    time.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")

    def _request_once(
        self,
        method: str,
        url: str,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        auth: tuple[str, str] | str | None = None,
        timeout: float | int | tuple[float, float] | None = None,
        allow_redirects: bool | None = None,
        proxies: str | dict[str, str] | None = None,
        proxy_auth: tuple[str, str] | None = None,
        verify: bool | None = None,
        stream: bool = False,
        cert: Any | None = None,
        json: Any | None = None,
        multipart: Multipart | None = None,
        referer: str | None = None,
        default_encoding: str | Callable[[bytes], str] | None = None,
        discard_cookies: bool | None = None,
    ) -> Response:
        """Execute a single request without retries."""
        # Prepare request kwargs using base class method
        prep, rnet_kwargs = self._prepare_request_kwargs(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            files=files,
            auth=auth,
            timeout=timeout,
            allow_redirects=allow_redirects,
            json=json,
            multipart=multipart,
            referer=referer,
        )

        # Make the request
        try:
            start_time = time.perf_counter()

            rnet_method, method_enum = self._get_rnet_method(method)

            if rnet_method is None:
                # Use the generic request method
                rnet_resp = self._client.request(method_enum, prep.url, **rnet_kwargs)
            else:
                rnet_resp = rnet_method(prep.url, **rnet_kwargs)

            elapsed_time = time.perf_counter() - start_time

            # Handle streaming vs non-streaming
            if stream:
                content = b""
                streamer = rnet_resp.stream()
            else:
                content = rnet_resp.bytes()
                streamer = None

            # Build response using base class method
            return self._build_response(
                rnet_resp=rnet_resp,
                prep=prep,
                content=content,
                streamer=streamer,
                stream=stream,
                elapsed_seconds=elapsed_time,
                default_encoding=default_encoding,
                discard_cookies=discard_cookies,
            )

        except HTTPError:
            # Re-raise HTTPError as-is (from raise_for_status)
            raise
        except Exception as e:
            raise convert_rnet_exception(e) from e

    def get(self, url: str, **kwargs: Any) -> Response:
        """Sends a GET request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", True)
        return self.request("GET", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Response:
        """Sends an OPTIONS request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", True)
        return self.request("OPTIONS", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Response:
        """Sends a HEAD request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", False)
        return self.request("HEAD", url, **kwargs)

    def post(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> Response:
        """Sends a POST request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) json data to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return self.request("POST", url, data=data, json=json, **kwargs)

    def put(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        """Sends a PUT request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return self.request("PUT", url, data=data, **kwargs)

    def patch(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        """Sends a PATCH request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return self.request("PATCH", url, data=data, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        """Sends a DELETE request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return self.request("DELETE", url, **kwargs)

    def send(self, request: PreparedRequest, **kwargs: Any) -> Response:
        """Send a given PreparedRequest.

        :rtype: requests.Response
        """
        return self.request(
            method=request.method or "GET",
            url=request.url or "",
            headers=dict(request.headers),
            data=request.body,
            cookies=request._cookies,
            **kwargs,
        )

    def ws_connect(self, url: str, **kwargs: Any) -> Any:
        """Connect to a WebSocket endpoint.

        Note: Synchronous WebSocket is not supported in rnet-requests.
        Use AsyncSession.ws_connect() instead.

        Raises:
            NotImplementedError: Always raised. Use AsyncSession for WebSocket.
        """
        raise NotImplementedError(
            "Synchronous WebSocket is not supported. "
            "Use AsyncSession.ws_connect() instead:\n\n"
            "  async with AsyncSession() as session:\n"
            "      async with session.ws_connect(url) as ws:\n"
            "          await ws.send_str('hello')\n"
        )

    def __repr__(self) -> str:
        return "<Session>"

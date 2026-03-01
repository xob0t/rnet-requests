"""
rnet_requests.async_session
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides an AsyncSession object for async HTTP requests,
providing a familiar requests-like interface while using rnet as the backend.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
)

from rnet import Client as RnetAsyncClient
from rnet import Proxy, Version

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
from .models import Response

if TYPE_CHECKING:
    from .multipart import Multipart
    from .websockets import AsyncWebSocket


class AsyncSession(SessionBase):
    """An async requests-compatible Session class backed by rnet.

    Provides cookie persistence, connection-pooling, and configuration.

    Basic Usage::

      >>> import asyncio
      >>> import rnet_requests
      >>> async def main():
      ...     async with rnet_requests.AsyncSession() as s:
      ...         r = await s.get('https://httpbin.org/get')
      ...         print(r.status_code)
      >>> asyncio.run(main())

    With browser impersonation::

      >>> async with rnet_requests.AsyncSession(impersonate='chrome') as s:
      ...     r = await s.get('https://tls.peet.ws/api/all')
    """

    _client: RnetAsyncClient

    def __init__(
        self,
        impersonate: str | Emulation | EmulationOption | None = None,
        impersonate_os: str | EmulationOS | None = None,
        client: RnetAsyncClient | None = None,
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
        """Initialize an AsyncSession.

        :param impersonate: Browser to impersonate. Can be a string like 'chrome',
            'firefox', 'safari', or an rnet Emulation enum value.
        :param impersonate_os: OS to impersonate. Can be 'windows', 'macos',
            'linux', 'android', 'ios', or an rnet EmulationOS enum value.
        :param client: An existing rnet Client to use.
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
            # Create the rnet async client
            self._client = RnetAsyncClient(**client_kwargs)

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        self._closed = True

    async def request(
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
        """Sends an async request.

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
                return await self._request_once(
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
                    await asyncio.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")

    async def _request_once(
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
        """Execute a single async request without retries."""
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

        # Make the async request
        try:
            start_time = time.perf_counter()

            rnet_method, method_enum = self._get_rnet_method(method)

            if rnet_method is None:
                # Use the generic request method
                rnet_resp = await self._client.request(
                    method_enum, prep.url, **rnet_kwargs
                )
            else:
                rnet_resp = await rnet_method(prep.url, **rnet_kwargs)

            elapsed_time = time.perf_counter() - start_time

            # Handle streaming vs non-streaming
            if stream:
                content = b""
                streamer = rnet_resp.stream()
            else:
                content = await rnet_resp.bytes()
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

    async def get(self, url: str, **kwargs: Any) -> Response:
        """Sends an async GET request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", True)
        return await self.request("GET", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> Response:
        """Sends an async OPTIONS request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", True)
        return await self.request("OPTIONS", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> Response:
        """Sends an async HEAD request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        kwargs.setdefault("allow_redirects", False)
        return await self.request("HEAD", url, **kwargs)

    async def post(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> Response:
        """Sends an async POST request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) json data to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return await self.request("POST", url, data=data, json=json, **kwargs)

    async def put(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        """Sends an async PUT request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return await self.request("PUT", url, data=data, **kwargs)

    async def patch(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        """Sends an async PATCH request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return await self.request("PATCH", url, data=data, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Response:
        """Sends an async DELETE request. Returns :class:`Response` object.

        :param url: URL for the new :class:`Request` object.
        :param \\*\\*kwargs: Optional arguments that ``request`` takes.
        :rtype: requests.Response
        """
        return await self.request("DELETE", url, **kwargs)

    async def ws_connect(
        self,
        url: str,
        *,
        autoclose: bool = True,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | str | None = None,
        protocols: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncWebSocket:
        """Connect to a WebSocket endpoint.

        Args:
            url: The WebSocket URL (ws:// or wss://).
            autoclose: Whether to auto-close on receiving close frame.
            headers: Optional headers to send.
            cookies: Optional cookies to send.
            auth: Optional authentication (tuple of (user, pass) or bearer token).
            protocols: Optional list of WebSocket subprotocols.
            **kwargs: Additional arguments passed to rnet's websocket method.

        Returns:
            An AsyncWebSocket instance.

        Example:
            >>> async with session.ws_connect("wss://echo.websocket.org") as ws:
            ...     await ws.send_str("Hello!")
            ...     msg = await ws.recv_str()
            ...     print(msg)
        """
        from .websockets import AsyncWebSocket

        # Merge headers
        merged_headers = dict(self.headers)
        if headers:
            merged_headers.update(headers)

        # Merge cookies
        merged_cookies = dict(self.cookies)
        if cookies:
            merged_cookies.update(cookies)

        # Build kwargs for rnet websocket
        ws_kwargs: dict[str, Any] = {}

        if merged_headers:
            ws_kwargs["headers"] = merged_headers
        if merged_cookies:
            ws_kwargs["cookies"] = merged_cookies
        if protocols:
            ws_kwargs["protocols"] = protocols

        # Handle auth
        effective_auth = auth or self.auth
        if effective_auth:
            if isinstance(effective_auth, tuple):
                ws_kwargs["basic_auth"] = effective_auth
            else:
                ws_kwargs["bearer_auth"] = effective_auth

        # Pass through any other kwargs
        ws_kwargs.update(kwargs)

        try:
            rnet_ws = await self._client.websocket(url, **ws_kwargs)
            return AsyncWebSocket(rnet_ws, session=self, autoclose=autoclose)
        except Exception as e:
            raise convert_rnet_exception(e) from e

    def __repr__(self) -> str:
        return "<AsyncSession>"

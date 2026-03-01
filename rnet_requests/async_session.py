"""
rnet_requests.async_session
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides an AsyncSession object for async HTTP requests,
providing a familiar requests-like interface while using rnet as the backend.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
)
from urllib.parse import urljoin, urlparse

from rnet import Client as RnetAsyncClient
from rnet import Identity, Part, Proxy, Version
from rnet import Multipart as RnetMultipart
from rnet.redirect import Policy

from .impersonate import (
    Emulation,
    EmulationOption,
    EmulationOS,
    create_emulation_option,
)
from .sessions import (
    HttpVersionLiteral,
    RetryStrategy,
    _normalize_retry,
    _resolve_http_version,
)

if TYPE_CHECKING:
    from .multipart import Multipart

from .cookies import Cookies
from .exceptions import (
    HTTPError,
    MissingSchema,
    SessionClosed,
    convert_rnet_exception,
)
from .models import Request, Response, _get_reason_phrase
from .structures import CaseInsensitiveDict


def _is_absolute_url(url: str) -> bool:
    """Check if the provided url is an absolute url"""
    parsed_url = urlparse(url)
    return bool(parsed_url.scheme and parsed_url.hostname)


class AsyncSession:
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
        max_redirects: int = 30,
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
        self._closed = False
        self._timeout = timeout
        self._verify = verify if verify is not None else True
        self._allow_redirects = allow_redirects
        self._max_redirects = max_redirects

        # curl_cffi compatible options
        self.retry = _normalize_retry(retry)
        self.default_encoding = default_encoding
        self.discard_cookies = discard_cookies
        self.raise_for_status = raise_for_status

        # Base URL for relative URLs
        if base_url and not _is_absolute_url(base_url):
            raise ValueError("You need to provide an absolute url for 'base_url'")
        self.base_url = base_url

        # Default params
        self.params = params or {}

        # Default headers
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict(headers or {})

        # Cookie storage - use Cookies class for curl_cffi compatibility
        self.cookies: Cookies = Cookies(cookies)

        # Auth
        self.auth: tuple[str, str] | str | None = auth

        # Proxy auth - warn if set (not yet implemented)
        self.proxy_auth = proxy_auth
        if proxy_auth:
            import warnings

            warnings.warn(
                "proxy_auth is not yet fully implemented. "
                "For now, include credentials in the proxy URL: "
                "http://user:pass@proxy.example.com:8080",
                UserWarning,
                stacklevel=2,
            )

        # Handle proxy vs proxies
        if proxy and proxies:
            raise TypeError("Cannot specify both 'proxy' and 'proxies'")
        if proxy:
            proxies = {"all": proxy}

        # Resolve HTTP version
        resolved_http_version = _resolve_http_version(http_version)

        # Resolve client certificate (identity)
        identity = None
        if cert is not None:
            if isinstance(cert, tuple):
                # (cert_path, key_path) - PKCS#8 PEM format
                cert_path, key_path = cert
                with open(cert_path, "rb") as f:
                    cert_data = f.read()
                with open(key_path, "rb") as f:
                    key_data = f.read()
                identity = Identity.from_pkcs8_pem(cert_data, key_data)
            else:
                # Single PEM file - need to extract cert and key
                # This is a limitation - rnet requires separate cert/key
                raise ValueError(
                    "Single PEM file not supported. "
                    "Use cert=(cert_path, key_path) with separate files."
                )

        # Create or use provided client
        if client is not None:
            self._client = client
        else:
            # Resolve emulation (impersonation)
            emulation_option = create_emulation_option(
                emulation=impersonate,
                os=impersonate_os,
            )

            # Resolve proxies
            proxy_list = self._resolve_proxies(proxies)

            # Determine redirect policy
            # rnet v3 uses Policy objects for redirect configuration
            if allow_redirects:
                redirect_policy = Policy.limited(max_redirects)
            else:
                redirect_policy = Policy.none()

            # Build client kwargs
            client_kwargs: dict[str, Any] = {
                "emulation": emulation_option,
                "redirect": redirect_policy,
                "cookie_store": not discard_cookies,
                "debug": debug,
            }

            # SSL verification (rnet uses danger_accept_invalid_certs)
            if not self._verify:
                client_kwargs["danger_accept_invalid_certs"] = True

            # Optional client parameters
            if user_agent:
                client_kwargs["user_agent"] = user_agent
            if self.headers and default_headers:
                client_kwargs["default_headers"] = dict(self.headers)
            if timeout is not None:
                if isinstance(timeout, tuple):
                    client_kwargs["timeout"] = timedelta(seconds=timeout[0])
                    client_kwargs["read_timeout"] = timedelta(seconds=timeout[1])
                else:
                    client_kwargs["timeout"] = timedelta(seconds=timeout)
            if proxy_list:
                client_kwargs["proxies"] = proxy_list
            if resolved_http_version:
                client_kwargs["http_version"] = resolved_http_version
            if interface:
                client_kwargs["interface"] = interface
            if identity:
                client_kwargs["identity"] = identity
            if not default_headers:
                client_kwargs["default_headers"] = False

            # Merge with any extra kwargs
            client_kwargs.update(kwargs)

            # Create the rnet async client
            self._client = RnetAsyncClient(**client_kwargs)

    def _resolve_proxies(
        self, proxies: str | dict[str, str] | list[Proxy] | None
    ) -> list[Proxy] | None:
        """Resolve proxies to a list of rnet Proxy objects."""
        if proxies is None:
            return None
        if isinstance(proxies, list):
            return proxies
        if isinstance(proxies, str):
            return [Proxy.all(proxies)]
        if isinstance(proxies, dict):
            result = []
            for scheme, url in proxies.items():
                if scheme.lower() == "http":
                    result.append(Proxy.http(url))
                elif scheme.lower() == "https":
                    result.append(Proxy.https(url))
                else:
                    result.append(Proxy.all(url))
            return result
        return None

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        self._closed = True

    def clear_cookies(self) -> None:
        """Clear all cookies from the session and underlying client."""
        self.cookies.clear()
        self._client.clear_cookies()

    def delete_cookie(self, name: str, url: str | None = None) -> None:
        """Delete a specific cookie from the session.

        :param name: The name of the cookie to delete.
        :param url: The URL associated with the cookie. If not provided,
            removes from session dict only. Provide URL to also remove
            from the underlying client's cookie store.
        """
        if name in self.cookies:
            del self.cookies[name]
        if url:
            import contextlib

            with contextlib.suppress(Exception):
                self._client.remove_cookie(url, name)

    def _retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        strategy = self.retry
        if strategy.backoff == "exponential":
            delay = strategy.delay * (2 ** (attempt - 1))
        else:
            delay = strategy.delay * attempt
        if strategy.jitter:
            delay += random.uniform(0.0, strategy.jitter)
        return delay

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
        if self._closed:
            raise SessionClosed("Session has been closed")

        if not url:
            raise MissingSchema("Missing URL")

        # Handle base_url for relative URLs
        if self.base_url and not _is_absolute_url(url):
            url = urljoin(self.base_url, url)

        # Merge default params with request params
        merged_params: dict[str, str] = dict(self.params)
        if params:
            if isinstance(params, dict):
                merged_params.update(params)
            else:
                merged_params.update(dict(params))

        # Prepare the request
        req = Request(
            method=method.upper(),
            url=url,
            headers=headers,
            files=files,
            data=data,
            json=json,
            params=merged_params if merged_params else None,
            auth=auth or self.auth,
            cookies=cookies,
        )
        prep = req.prepare()

        # Merge with session headers
        merged_headers = dict(self.headers)
        if prep.headers:
            merged_headers.update(prep.headers)

        # Add referer shortcut
        if referer:
            merged_headers["Referer"] = referer

        # Merge cookies - get dict from Cookies class
        merged_cookies = self.cookies.get_dict()
        if cookies:
            if isinstance(cookies, Cookies):
                merged_cookies.update(cookies.get_dict())
            else:
                merged_cookies.update(cookies)

        # Build rnet request kwargs
        rnet_kwargs: dict[str, Any] = {}

        # Headers
        if merged_headers:
            rnet_kwargs["headers"] = merged_headers

        # Cookies
        if merged_cookies:
            rnet_kwargs["cookies"] = merged_cookies

        # Query params
        if merged_params:
            rnet_kwargs["query"] = list(merged_params.items())

        # Body data
        if json is not None:
            rnet_kwargs["json"] = json
        elif data is not None:
            if isinstance(data, dict):
                rnet_kwargs["form"] = list(data.items())
            elif isinstance(data, list):
                rnet_kwargs["form"] = data
            elif isinstance(data, (str, bytes)):
                rnet_kwargs["body"] = data

        # Files/multipart
        if multipart is not None:
            # Use the Multipart object directly
            from .multipart import Multipart as MultipartWrapper

            if isinstance(multipart, MultipartWrapper):
                rnet_kwargs["multipart"] = multipart._to_rnet_multipart()
            else:
                # Assume it's already a rnet Multipart
                rnet_kwargs["multipart"] = multipart
        elif files:
            parts = []
            for name, file_info in files.items():
                if isinstance(file_info, tuple):
                    filename = file_info[0]
                    content = file_info[1]
                    mime = file_info[2] if len(file_info) > 2 else None
                    # Read file-like objects
                    if hasattr(content, "read"):
                        content = content.read()
                    parts.append(Part(name, content, filename=filename, mime=mime))
                else:
                    # Direct file object or content
                    content = file_info
                    if hasattr(content, "read"):
                        content = content.read()
                        # Try to get filename from file object
                        filename = getattr(file_info, "name", name)
                        if hasattr(filename, "__fspath__"):
                            filename = str(filename)
                        elif "/" in str(filename) or "\\" in str(filename):
                            import os

                            filename = os.path.basename(filename)
                        parts.append(Part(name, content, filename=filename))
                    else:
                        parts.append(Part(name, content))
            rnet_kwargs["multipart"] = RnetMultipart(*parts)

        # Timeout
        effective_timeout = timeout if timeout is not None else self._timeout
        if effective_timeout is not None:
            if isinstance(effective_timeout, tuple):
                # (connect_timeout, read_timeout) - rnet v3 uses timedelta
                rnet_kwargs["timeout"] = timedelta(seconds=effective_timeout[0])
                rnet_kwargs["read_timeout"] = timedelta(seconds=effective_timeout[1])
            else:
                rnet_kwargs["timeout"] = timedelta(seconds=effective_timeout)

        # Redirects
        effective_redirects = (
            allow_redirects if allow_redirects is not None else self._allow_redirects
        )
        rnet_kwargs["allow_redirects"] = effective_redirects
        rnet_kwargs["max_redirects"] = self._max_redirects

        # Auth
        effective_auth = auth or self.auth
        if effective_auth:
            if isinstance(effective_auth, tuple):
                rnet_kwargs["basic_auth"] = effective_auth
            else:
                rnet_kwargs["auth"] = effective_auth

        # Make the async request
        try:
            start_time = time.perf_counter()

            method_lower = method.lower()
            rnet_method = getattr(self._client, method_lower, None)

            if rnet_method is None:
                # Use the generic request method
                from rnet import Method

                method_enum = getattr(Method, method.upper())
                rnet_resp = await self._client.request(method_enum, url, **rnet_kwargs)
            else:
                rnet_resp = await rnet_method(url, **rnet_kwargs)

            elapsed_time = time.perf_counter() - start_time

            # Read response metadata before consuming content
            # rnet v3: status is a StatusCode object, use .as_int() to get int
            status = rnet_resp.status.as_int()
            url_final = rnet_resp.url
            encoding = getattr(rnet_resp, "encoding", None) or "utf-8"

            # Get headers before consuming (rnet v3 HeaderMap uses keys()/get())
            headers_dict: dict[str, str] = {}
            for key in rnet_resp.headers.keys():  # noqa: SIM118
                # Keys are bytes in rnet v3
                key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
                value = rnet_resp.headers.get(key_str)
                if value is not None:
                    value_str = (
                        value.decode("utf-8")
                        if isinstance(value, bytes)
                        else str(value)
                    )
                    headers_dict[key_str] = value_str

            # Get cookies before consuming
            cookies_list = list(rnet_resp.cookies)

            # Read the response content (consumes the response body)
            content = await rnet_resp.bytes()

            # Determine encoding
            effective_encoding = default_encoding or self.default_encoding
            if callable(effective_encoding):
                final_encoding = effective_encoding(content)
            else:
                final_encoding = effective_encoding or encoding

            # Create our Response object from metadata + content
            response = Response()
            response._content = content
            response._content_consumed = True
            response.status_code = status
            response.url = url_final
            response.encoding = final_encoding
            response.headers = CaseInsensitiveDict(headers_dict)
            response.default_encoding = self.default_encoding

            # Set cookies from response (direct response cookies)
            # Use Cookies class for curl_cffi compatibility
            response.cookies = Cookies()
            for cookie in cookies_list:
                response.cookies.set(cookie.name, cookie.value)

            # Also get cookies from client's cookie jar (captures redirect cookies)
            # rnet v3 uses cookie_jar.get_all() to get all cookies
            try:
                cookie_jar = self._client.cookie_jar
                if cookie_jar:
                    for cookie in cookie_jar.get_all():
                        if cookie.name not in response.cookies:
                            response.cookies.set(cookie.name, cookie.value)
            except (AttributeError, TypeError):
                # Cookie jar not available or incompatible API
                pass

            # Set reason from status code
            response.reason = _get_reason_phrase(status)
            response.request = prep

            # Set elapsed time
            response.elapsed = timedelta(seconds=elapsed_time)

            # Populate redirect history from rnet response
            response.history = []
            if hasattr(rnet_resp, "history") and rnet_resp.history:
                for hist in rnet_resp.history:
                    hist_response = Response()
                    hist_response.status_code = hist.status
                    hist_response.url = hist.url
                    hist_response.reason = _get_reason_phrase(hist.status)
                    # Convert headers
                    hist_headers: dict[str, str] = {}
                    for key in hist.headers.keys():  # noqa: SIM118
                        key_str = (
                            key.decode("utf-8") if isinstance(key, bytes) else str(key)
                        )
                        value = hist.headers.get(key_str)
                        if value is not None:
                            hist_headers[key_str] = (
                                value.decode("utf-8")
                                if isinstance(value, bytes)
                                else str(value)
                            )
                    hist_response.headers = CaseInsensitiveDict(hist_headers)
                    hist_response.cookies = Cookies()
                    hist_response._content = b""
                    hist_response._content_consumed = True
                    response.history.append(hist_response)

            # Update session cookies from response cookies (unless discarding)
            effective_discard = (
                discard_cookies if discard_cookies is not None else self.discard_cookies
            )
            if not effective_discard:
                for name, value in response.cookies.items():
                    self.cookies[name] = value

            # Raise for status if configured
            if self.raise_for_status:
                response.raise_for_status()

            return response

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


# Import at end to avoid circular import
from .websockets import AsyncWebSocket  # noqa: E402

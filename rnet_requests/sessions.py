"""
rnet_requests.sessions
~~~~~~~~~~~~~~~~~~~~~~

This module provides a Session object that manages settings across requests,
providing a familiar requests-like interface while using rnet as the backend.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
)
from urllib.parse import urljoin

from rnet import (
    Identity,
    Part,
    Proxy,
    Version,
)
from rnet import (
    Multipart as RnetMultipart,
)
from rnet.blocking import Client as BlockingClient
from rnet.redirect import Policy

from .cookies import Cookies
from .exceptions import (
    HTTPError,
    MissingSchema,
    SessionClosed,
    convert_rnet_exception,
)
from .impersonate import (
    Emulation,
    EmulationOption,
    EmulationOS,
    create_emulation_option,
)
from .models import PreparedRequest, Request, Response
from .structures import CaseInsensitiveDict

if TYPE_CHECKING:
    from .multipart import Multipart

# Type aliases
RetryBackoff = Literal["linear", "exponential"]
HttpVersionLiteral = Literal["HTTP/1.0", "HTTP/1.1", "HTTP/2", "HTTP/3"]


@dataclass
class RetryStrategy:
    """Retry strategy configuration for failed requests.

    Attributes:
        count: Number of retries to attempt.
        delay: Base delay between retries in seconds.
        jitter: Random jitter to add to delay (0 to jitter seconds).
        backoff: Backoff strategy - "linear" or "exponential".
            - "linear": delay increases linearly (delay * attempt)
            - "exponential": delay doubles each attempt (delay * 2^(attempt-1))

    Example:
        With delay=1.0:
        - linear backoff: 1s, 2s, 3s, ...
        - exponential backoff: 1s, 2s, 4s, 8s, ...
    """

    count: int
    delay: float = 0.0
    jitter: float = 0.0
    backoff: RetryBackoff = "linear"


def _normalize_retry(retry: int | RetryStrategy | None) -> RetryStrategy:
    """Normalize retry parameter to RetryStrategy."""
    if retry is None:
        retry = 0
    if isinstance(retry, RetryStrategy):
        strategy = retry
    elif isinstance(retry, int):
        strategy = RetryStrategy(count=retry)
    else:
        raise TypeError("retry must be an int or RetryStrategy")
    if strategy.count < 0:
        raise ValueError("retry.count must be >= 0")
    if strategy.delay < 0:
        raise ValueError("retry.delay must be >= 0")
    if strategy.jitter < 0:
        raise ValueError("retry.jitter must be >= 0")
    if strategy.backoff not in ("linear", "exponential"):
        raise ValueError("retry.backoff must be 'linear' or 'exponential'")
    return strategy


def _resolve_http_version(
    version: Version | HttpVersionLiteral | None,
) -> Version | None:
    """Resolve HTTP version string to rnet Version enum."""
    if version is None:
        return None
    if isinstance(version, Version):
        return version
    version_map = {
        "HTTP/1.0": Version.HTTP_10,
        "HTTP/1.1": Version.HTTP_11,
        "HTTP/2": Version.HTTP_2,
        "HTTP/3": Version.HTTP_3,
    }
    if version in version_map:
        return version_map[version]
    raise ValueError(f"Invalid HTTP version: {version}")


def _is_absolute_url(url: str) -> bool:
    """Check if the provided url is an absolute url"""
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    return bool(parsed_url.scheme and parsed_url.hostname)


class Session:
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

            # Create the rnet client
            self._client = BlockingClient(**client_kwargs)

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

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Closes all adapters and as such the session."""
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

        # Make the request
        try:
            start_time = time.perf_counter()

            method_lower = method.lower()
            rnet_method = getattr(self._client, method_lower, None)

            if rnet_method is None:
                # Use the generic request method
                from rnet import Method

                method_enum = getattr(Method, method.upper())
                rnet_resp = self._client.request(method_enum, url, **rnet_kwargs)
            else:
                rnet_resp = rnet_method(url, **rnet_kwargs)

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

            # Get cookies from response (for non-redirect responses)
            cookies_list = list(rnet_resp.cookies)

            # Read the response content (consumes the response body)
            content = rnet_resp.bytes()

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
            from .models import _get_reason_phrase

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

    def prepare_request(self, request: Request) -> PreparedRequest:
        """Constructs a :class:`PreparedRequest <PreparedRequest>` for
        transmission and returns it. The :class:`PreparedRequest` has settings
        merged from the :class:`Request <Request>` instance and those of the
        :class:`Session`.

        :param request: :class:`Request` instance to prepare with this
            session's settings.
        :rtype: requests.PreparedRequest
        """
        # Merge cookies
        cookies = dict(self.cookies)
        if request.cookies:
            cookies.update(request.cookies)

        # Merge headers
        headers = dict(self.headers)
        if request.headers:
            headers.update(request.headers)

        # Prepare
        p = request.prepare()
        p.headers = CaseInsensitiveDict(headers)
        p._cookies = cookies

        return p

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

    def mount(self, prefix: str, adapter: Any) -> None:
        """Registers a connection adapter to a prefix.

        Note: rnet handles adapters internally, this is a no-op for compatibility.
        """
        pass

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

"""
rnet_requests.base
~~~~~~~~~~~~~~~~~~

This module provides base classes and shared logic for Session classes.
"""

from __future__ import annotations

import contextlib
import os
import random
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
)
from urllib.parse import urljoin, urlparse

from rnet import (
    Identity,
    Method,
    Part,
    Proxy,
    Version,
)
from rnet import Multipart as RnetMultipart
from rnet.redirect import Policy

from .cookies import Cookies
from .exceptions import (
    MissingSchema,
    SessionClosed,
)
from .impersonate import (
    Emulation,
    EmulationOption,
    EmulationOS,
    create_emulation_option,
)
from .models import PreparedRequest, Request, Response, _get_reason_phrase
from .structures import CaseInsensitiveDict

if TYPE_CHECKING:
    from .multipart import Multipart

# Type aliases
RetryBackoff = Literal["linear", "exponential"]
HttpVersionLiteral = Literal["HTTP/1.0", "HTTP/1.1", "HTTP/2", "HTTP/3"]

# Constants
DEFAULT_MAX_REDIRECTS = 30
DEFAULT_CHUNK_SIZE = 512


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


def normalize_retry(retry: int | RetryStrategy | None) -> RetryStrategy:
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


def resolve_http_version(
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


def is_absolute_url(url: str) -> bool:
    """Check if the provided url is an absolute url."""
    parsed_url = urlparse(url)
    return bool(parsed_url.scheme and parsed_url.hostname)


def resolve_proxies(
    proxies: str | dict[str, str] | list[Proxy] | None,
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


def build_rnet_multipart(files: dict[str, Any]) -> RnetMultipart:
    """Build rnet Multipart from files dict."""
    parts = []
    for name, file_info in files.items():
        if isinstance(file_info, tuple):
            filename = file_info[0]
            content = file_info[1]
            mime = file_info[2] if len(file_info) > 2 else None
            # Pass file-like objects directly to rnet for streaming
            # Don't call .read() - rnet handles streaming internally
            parts.append(Part(name, content, filename=filename, mime=mime))
        else:
            # Direct file object or content
            content = file_info
            if hasattr(content, "read"):
                # Try to get filename from file object
                filename = getattr(file_info, "name", name)
                if hasattr(filename, "__fspath__"):
                    filename = str(filename)
                elif "/" in str(filename) or "\\" in str(filename):
                    filename = os.path.basename(filename)
                # Pass file handle directly for streaming
                parts.append(Part(name, content, filename=filename))
            else:
                parts.append(Part(name, content))
    return RnetMultipart(*parts)


def convert_headers_dict(headers: Any) -> dict[str, str]:
    """Convert rnet headers to dict[str, str]."""
    headers_dict: dict[str, str] = {}
    for key in headers.keys():  # noqa: SIM118 - rnet v3 API requires .keys()
        # Keys are bytes in rnet v3
        key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        value = headers.get(key_str)
        if value is not None:
            value_str = (
                value.decode("utf-8") if isinstance(value, bytes) else str(value)
            )
            headers_dict[key_str] = value_str
    return headers_dict


def build_history_response(hist: Any) -> Response:
    """Build a Response object from rnet history item."""
    hist_response = Response()
    hist_response.status_code = hist.status
    hist_response.url = hist.url
    hist_response.reason = _get_reason_phrase(hist.status)
    hist_response.headers = CaseInsensitiveDict(convert_headers_dict(hist.headers))
    hist_response.cookies = Cookies()
    hist_response._content = b""
    hist_response._content_consumed = True
    return hist_response


class SessionBase:
    """Base class with shared logic for Session and AsyncSession.

    This class contains all the initialization logic, proxy resolution,
    cookie management, and request preparation that is common to both
    synchronous and asynchronous sessions.
    """

    # These will be set by subclasses
    _client: Any
    _closed: bool
    _timeout: float | tuple[float, float] | None
    _verify: bool
    _allow_redirects: bool
    _max_redirects: int
    retry: RetryStrategy
    default_encoding: str | Callable[[bytes], str]
    discard_cookies: bool
    raise_for_status: bool
    base_url: str | None
    params: dict[str, str]
    headers: CaseInsensitiveDict
    cookies: Cookies
    auth: tuple[str, str] | str | None
    proxy_auth: tuple[str, str] | None

    def _init_session(
        self,
        impersonate: str | Emulation | EmulationOption | None,
        impersonate_os: str | EmulationOS | None,
        timeout: float | tuple[float, float] | None,
        verify: bool | None,
        proxies: str | dict[str, str] | list[Proxy] | None,
        proxy: str | None,
        proxy_auth: tuple[str, str] | None,
        allow_redirects: bool,
        max_redirects: int,
        base_url: str | None,
        params: dict[str, str] | None,
        retry: int | RetryStrategy | None,
        user_agent: str | None,
        headers: dict[str, str] | None,
        cookies: dict[str, str] | None,
        auth: tuple[str, str] | None,
        http_version: Version | HttpVersionLiteral | None,
        default_headers: bool,
        default_encoding: str | Callable[[bytes], str],
        interface: str | None,
        cert: str | tuple[str, str] | None,
        debug: bool,
        discard_cookies: bool,
        raise_for_status: bool,
        extra_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Initialize session state and return client kwargs.

        This method sets up all the session state and returns the kwargs
        needed to create the rnet client.
        """
        self._closed = False
        self._timeout = timeout
        self._verify = verify if verify is not None else True
        self._allow_redirects = allow_redirects
        self._max_redirects = max_redirects

        # curl_cffi compatible options
        self.retry = normalize_retry(retry)
        self.default_encoding = default_encoding
        self.discard_cookies = discard_cookies
        self.raise_for_status = raise_for_status

        # Base URL for relative URLs
        if base_url and not is_absolute_url(base_url):
            raise ValueError("You need to provide an absolute url for 'base_url'")
        self.base_url = base_url

        # Default params
        self.params = params or {}

        # Default headers
        self.headers = CaseInsensitiveDict(headers or {})

        # Cookie storage - use Cookies class for curl_cffi compatibility
        self.cookies = Cookies(cookies)

        # Auth
        self.auth = auth

        # Proxy auth - warn if set (not yet implemented)
        self.proxy_auth = proxy_auth
        if proxy_auth:
            warnings.warn(
                "proxy_auth is not yet fully implemented. "
                "For now, include credentials in the proxy URL: "
                "http://user:pass@proxy.example.com:8080",
                UserWarning,
                stacklevel=3,
            )

        # Handle proxy vs proxies
        if proxy and proxies:
            raise TypeError("Cannot specify both 'proxy' and 'proxies'")
        if proxy:
            proxies = {"all": proxy}

        # Resolve HTTP version
        resolved_http_version = resolve_http_version(http_version)

        # Resolve client certificate (identity)
        identity = self._resolve_identity(cert)

        # Resolve emulation (impersonation)
        emulation_option = create_emulation_option(
            emulation=impersonate,
            os=impersonate_os,
        )

        # Resolve proxies
        proxy_list = resolve_proxies(proxies)

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
        client_kwargs.update(extra_kwargs)

        return client_kwargs

    def _resolve_identity(self, cert: str | tuple[str, str] | None) -> Identity | None:
        """Resolve client certificate to Identity object."""
        if cert is None:
            return None
        if isinstance(cert, tuple):
            # (cert_path, key_path) - PKCS#8 PEM format
            cert_path, key_path = cert
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            with open(key_path, "rb") as f:
                key_data = f.read()
            return Identity.from_pkcs8_pem(cert_data, key_data)
        else:
            # Single PEM file - need to extract cert and key
            # This is a limitation - rnet requires separate cert/key
            raise ValueError(
                "Single PEM file not supported. "
                "Use cert=(cert_path, key_path) with separate files."
            )

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

    def _prepare_request_kwargs(
        self,
        method: str,
        url: str,
        params: dict[str, str] | list[tuple[str, str]] | None,
        data: dict[str, Any] | list[tuple[str, str]] | str | bytes | None,
        headers: dict[str, str] | None,
        cookies: dict[str, str] | None,
        files: dict[str, Any] | None,
        auth: tuple[str, str] | str | None,
        timeout: float | int | tuple[float, float] | None,
        allow_redirects: bool | None,
        json: Any | None,
        multipart: Multipart | None,
        referer: str | None,
    ) -> tuple[PreparedRequest, dict[str, Any]]:
        """Prepare request and build rnet kwargs.

        Returns:
            Tuple of (PreparedRequest, rnet_kwargs dict)
        """
        if self._closed:
            raise SessionClosed("Session has been closed")

        if not url:
            raise MissingSchema("Missing URL")

        # Handle base_url for relative URLs
        if self.base_url and not is_absolute_url(url):
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
            rnet_kwargs["multipart"] = build_rnet_multipart(files)

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

        return prep, rnet_kwargs

    def _get_rnet_method(self, method: str) -> tuple[Any, Any]:
        """Get the rnet method to call.

        Returns:
            Tuple of (method_func, method_enum_or_none)
            If method_func is None, use generic request with method_enum
        """
        method_lower = method.lower()
        rnet_method = getattr(self._client, method_lower, None)

        if rnet_method is None:
            method_enum = getattr(Method, method.upper())
            return None, method_enum
        return rnet_method, None

    def _build_response(
        self,
        rnet_resp: Any,
        prep: PreparedRequest,
        content: bytes,
        streamer: Any,
        stream: bool,
        elapsed_seconds: float,
        default_encoding: str | Callable[[bytes], str] | None,
        discard_cookies: bool | None,
    ) -> Response:
        """Build Response object from rnet response.

        This handles all the common response building logic.
        """
        # Read response metadata
        # rnet v3: status is a StatusCode object, use .as_int() to get int
        status = rnet_resp.status.as_int()
        url_final = rnet_resp.url
        encoding = getattr(rnet_resp, "encoding", None) or "utf-8"

        # Get headers
        headers_dict = convert_headers_dict(rnet_resp.headers)

        # Get cookies from response
        cookies_list = list(rnet_resp.cookies)

        # Determine encoding
        effective_encoding = default_encoding or self.default_encoding
        if callable(effective_encoding) and not stream:
            final_encoding = effective_encoding(content)
        elif isinstance(effective_encoding, str):
            final_encoding = effective_encoding
        else:
            final_encoding = encoding

        # Create our Response object from metadata + content
        response = Response()
        response._content = content if not stream else None
        response._content_consumed = not stream
        response._is_stream = stream
        response._streamer = streamer
        response._rnet_response = rnet_resp
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
        response.elapsed = timedelta(seconds=elapsed_seconds)

        # Populate redirect history from rnet response
        response.history = []
        if hasattr(rnet_resp, "history") and rnet_resp.history:
            for hist in rnet_resp.history:
                response.history.append(build_history_response(hist))

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
        merged_cookies = dict(self.cookies)
        if request.cookies:
            merged_cookies.update(request.cookies)

        # Merge headers
        merged_headers = dict(self.headers)
        if request.headers:
            merged_headers.update(request.headers)

        # Prepare
        p = request.prepare()
        p.headers = CaseInsensitiveDict(merged_headers)
        p._cookies = merged_cookies

        return p

    def mount(self, prefix: str, adapter: Any) -> None:
        """Registers a connection adapter to a prefix.

        Note: rnet handles adapters internally, this is a no-op for compatibility.
        """
        pass

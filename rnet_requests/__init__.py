"""
rnet-requests: A curl_cffi-compatible API wrapper for rnet.

This module provides a familiar curl_cffi-like interface while leveraging
rnet's advanced features like browser impersonation and TLS fingerprinting.

Basic usage (sync):
    >>> import rnet_requests as requests
    >>> r = requests.get('https://httpbin.org/get')
    >>> r.status_code
    200
    >>> r.json()
    {...}

Basic usage (async):
    >>> import asyncio
    >>> import rnet_requests
    >>> async def main():
    ...     async with rnet_requests.AsyncSession() as s:
    ...         r = await s.get('https://httpbin.org/get')
    ...         print(r.json())
    >>> asyncio.run(main())

With Session (recommended for multiple requests):
    >>> s = requests.Session()
    >>> s.get('https://httpbin.org/cookies/set/foo/bar')
    >>> r = s.get('https://httpbin.org/cookies')
    >>> r.json()
    {'cookies': {'foo': 'bar'}}

With browser impersonation:
    >>> s = requests.Session(impersonate='chrome')
    >>> r = s.get('https://tls.peet.ws/api/all')

WebSocket support:
    >>> async def ws_example():
    ...     async with rnet_requests.AsyncSession() as s:
    ...         async with s.ws_connect("wss://echo.websocket.org") as ws:
    ...             await ws.send_str("Hello!")
    ...             msg = await ws.recv_str()
    ...             print(msg)
"""

__all__ = [
    # Module-level sync functions (curl_cffi compatible)
    "request",
    "head",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    # Async module-level functions (for backward compatibility)
    "async_request",
    "async_get",
    "async_post",
    "async_put",
    "async_patch",
    "async_delete",
    "async_head",
    "async_options",
    # Sessions
    "Session",
    "AsyncSession",
    # Emulation (rnet v3 naming)
    "Emulation",
    "EmulationOS",
    "EmulationOption",
    # Impersonation (backward compatibility aliases)
    "Impersonate",
    "ImpersonateOption",
    "ImpersonateOS",
    # Browser/OS types
    "BrowserType",
    "BrowserTypeLiteral",
    "OSType",
    "OSTypeLiteral",
    # Models
    "Response",
    "Request",
    # Headers and Cookies
    "Headers",
    "Cookies",
    "CookieTypes",
    "HeaderTypes",
    "CaseInsensitiveDict",
    # Multipart
    "Multipart",
    # WebSocket
    "AsyncWebSocket",
    "WebSocketError",
    "WebSocketClosed",
    "WebSocketTimeout",
    "WsCloseCode",
    # Exceptions
    "RequestException",
    "HTTPError",
    "ConnectionError",
    "Timeout",
    "TooManyRedirects",
    "SessionClosed",
    "ConnectTimeout",
    "ReadTimeout",
    "URLRequired",
    "JSONDecodeError",
    "exceptions",
    # Proxy
    "ProxySpec",
    # Retry
    "RetryStrategy",
    # Version
    "__version__",
]

# Version
__version__ = "0.1.0"

# Exceptions (import early to avoid issues)
from . import exceptions

# Sync API (curl_cffi compatible - module level functions)
from .api import (
    delete,
    get,
    head,
    options,
    patch,
    post,
    put,
    request,
)

# Async module-level functions (for backward compatibility)
from .async_api import delete as async_delete
from .async_api import get as async_get
from .async_api import head as async_head
from .async_api import options as async_options
from .async_api import patch as async_patch
from .async_api import post as async_post
from .async_api import put as async_put
from .async_api import request as async_request

# Sessions
from .async_session import AsyncSession

# Cookies and Headers (curl_cffi compatible)
from .cookies import Cookies, CookieTypes
from .exceptions import (
    ConnectionError,
    ConnectTimeout,
    HTTPError,
    JSONDecodeError,
    ReadTimeout,
    RequestException,
    SessionClosed,
    Timeout,
    TooManyRedirects,
    URLRequired,
)
from .headers import Headers, HeaderTypes

# Emulation/Impersonation
from .impersonate import (
    BrowserType,
    BrowserTypeLiteral,
    Emulation,
    EmulationOption,
    EmulationOS,
    Impersonate,
    ImpersonateOption,
    ImpersonateOS,
    OSType,
    OSTypeLiteral,
)

# Models
from .models import Request, Response

# Multipart
from .multipart import Multipart
from .sessions import RetryStrategy, Session

# Structures (backward compatibility)
from .structures import CaseInsensitiveDict

# WebSocket
from .websockets import (
    AsyncWebSocket,
    WebSocketClosed,
    WebSocketError,
    WebSocketTimeout,
    WsCloseCode,
)

# Type alias for proxy spec
ProxySpec = dict[str, str]

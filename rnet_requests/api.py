"""
rnet_requests.api
~~~~~~~~~~~~~~~~~

This module implements the requests-compatible API.
"""

from typing import Any

from .models import Response
from .sessions import Session


def request(
    method: str,
    url: str,
    **kwargs: Any,
) -> Response:
    """Constructs and sends a :class:`Request <Request>`.

    :param method: method for the new :class:`Request` object: ``GET``, ``OPTIONS``,
        ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary, list of tuples or bytes to send
        in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the
        body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary or list of tuples
        ``(filename, fileobj)``, ``(filename, fileobj, content_type)`` or
        ``(filename, fileobj, content_type, custom_headers)``, where
        ``fileobj`` is a string, bytes, or file-like object.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How many seconds to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Boolean. Enable/disable
        GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to
        ``True``.
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) Either a boolean, in which case it controls
        whether we verify the server's TLS certificate, or a string, in which
        case it must be a path to a CA bundle to use. Defaults to ``True``.
    :param stream: (optional) if ``False``, the response content will be
        immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair.
    :param impersonate: (optional) Browser to impersonate. Can be 'chrome',
        'firefox', 'safari', etc.
    :param impersonate_os: (optional) OS to impersonate. Can be 'windows',
        'macos', 'linux', 'android', 'ios'.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response

    Usage::

      >>> import rnet_requests as requests
      >>> req = requests.request('GET', 'https://httpbin.org/get')
      >>> req
      <Response [200]>
    """
    # Extract session-level kwargs
    impersonate = kwargs.pop("impersonate", None)
    impersonate_os = kwargs.pop("impersonate_os", None)

    with Session(impersonate=impersonate, impersonate_os=impersonate_os) as session:
        return session.request(method=method, url=url, **kwargs)


def get(url: str, params: Any | None = None, **kwargs: Any) -> Response:
    r"""Sends a GET request.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary, list of tuples or bytes to send
        in the query string for the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("GET", url, params=params, **kwargs)


def options(url: str, **kwargs: Any) -> Response:
    r"""Sends an OPTIONS request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("OPTIONS", url, **kwargs)


def head(url: str, **kwargs: Any) -> Response:
    r"""Sends a HEAD request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    kwargs.setdefault("allow_redirects", False)
    return request("HEAD", url, **kwargs)


def post(url: str, data: Any = None, json: Any = None, **kwargs: Any) -> Response:
    r"""Sends a POST request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json data to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("POST", url, data=data, json=json, **kwargs)


def put(url: str, data: Any = None, **kwargs: Any) -> Response:
    r"""Sends a PUT request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("PUT", url, data=data, **kwargs)


def patch(url: str, data: Any = None, **kwargs: Any) -> Response:
    r"""Sends a PATCH request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("PATCH", url, data=data, **kwargs)


def delete(url: str, **kwargs: Any) -> Response:
    r"""Sends a DELETE request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return request("DELETE", url, **kwargs)

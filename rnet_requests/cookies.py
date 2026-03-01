"""
rnet_requests.cookies
~~~~~~~~~~~~~~~~~~~~~

HTTP Cookies implementation compatible with curl_cffi.
Based on httpx's Cookies implementation.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from http.cookiejar import Cookie, CookieJar
from typing import Union

CookieTypes = Union["Cookies", CookieJar, dict, list[tuple[str, str]]]


@dataclass
class CookieMorsel:
    """Represents a single cookie with all its attributes."""

    name: str
    value: str
    domain: str = ""
    path: str = "/"
    secure: bool = False
    expires: int = 0
    http_only: bool = False

    def to_cookiejar_cookie(self) -> Cookie:
        """Convert to http.cookiejar.Cookie."""
        return Cookie(
            version=0,
            name=self.name,
            value=self.value,
            port=None,
            port_specified=False,
            domain=self.domain,
            domain_specified=bool(self.domain),
            domain_initial_dot=bool(self.domain.startswith(".")),
            path=self.path,
            path_specified=bool(self.path),
            secure=self.secure,
            expires=None if self.expires == 0 else self.expires,
            discard=self.expires == 0,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": str(self.http_only)},
            rfc2109=False,
        )

    @classmethod
    def from_cookiejar_cookie(cls, cookie: Cookie) -> CookieMorsel:
        """Create from http.cookiejar.Cookie."""
        return cls(
            name=cookie.name,
            value=cookie.value or "",
            domain=cookie.domain,
            path=cookie.path,
            secure=cookie.secure,
            expires=int(cookie.expires or 0),
            http_only=False,
        )


cut_port_re = re.compile(r":\d+$", re.ASCII)
IPV4_RE = re.compile(r"\.\d+$", re.ASCII)


class Cookies(MutableMapping[str, str]):
    """
    HTTP Cookies, as a mutable mapping.

    Compatible with curl_cffi's Cookies class.
    """

    def __init__(self, cookies: CookieTypes | None = None) -> None:
        if cookies is None or isinstance(cookies, dict):
            self.jar = CookieJar()
            if isinstance(cookies, dict):
                for key, value in cookies.items():
                    self.set(key, value)
        elif isinstance(cookies, list):
            self.jar = CookieJar()
            for key, value in cookies:
                self.set(key, value)
        elif isinstance(cookies, Cookies):
            self.jar = CookieJar()
            for cookie in cookies.jar:
                self.jar.set_cookie(cookie)
        elif isinstance(cookies, CookieJar):
            self.jar = cookies
        else:
            self.jar = CookieJar()

    def set(
        self,
        name: str,
        value: str,
        domain: str = "",
        path: str = "/",
        secure: bool = False,
    ) -> None:
        """
        Set a cookie value by name. May optionally include domain and path.
        """
        # Handle special cookie prefixes per spec
        if name.startswith("__Secure-") and secure is False:
            secure = True
        elif name.startswith("__Host-") and (secure is False or domain or path != "/"):
            secure = True
            domain = ""
            path = "/"

        cookie = Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=bool(domain),
            domain_initial_dot=domain.startswith(".") if domain else False,
            path=path,
            path_specified=bool(path),
            secure=secure,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": None},
            rfc2109=False,
        )
        self.jar.set_cookie(cookie)

    def get(
        self,
        name: str,
        default: str | None = None,
        domain: str | None = None,
        path: str | None = None,
    ) -> str | None:
        """
        Get a cookie by name. May optionally include domain and path
        in order to specify exactly which cookie to retrieve.
        """
        value = None
        for cookie in self.jar:
            if (
                cookie.name == name
                and (domain is None or cookie.domain == domain)
                and (path is None or cookie.path == path)
            ):
                value = cookie.value

        if value is None:
            return default
        return value

    def get_dict(self, domain: str | None = None, path: str | None = None) -> dict:
        """
        Get cookies as a dictionary.

        Note: Cookies with the same name on different domains may overwrite each other.
        """
        ret = {}
        for cookie in self.jar:
            if (domain is None or cookie.domain == domain) and (
                path is None or cookie.path == path
            ):
                ret[cookie.name] = cookie.value
        return ret

    def delete(
        self,
        name: str,
        domain: str | None = None,
        path: str | None = None,
    ) -> None:
        """
        Delete a cookie by name. May optionally include domain and path
        in order to specify exactly which cookie to delete.
        """
        if domain is not None and path is not None:
            return self.jar.clear(domain, path, name)

        remove = [
            cookie
            for cookie in self.jar
            if cookie.name == name
            and (domain is None or cookie.domain == domain)
            and (path is None or cookie.path == path)
        ]

        for cookie in remove:
            self.jar.clear(cookie.domain, cookie.path, cookie.name)

    def clear(self, domain: str | None = None, path: str | None = None) -> None:
        """
        Delete all cookies. Optionally include a domain and path in
        order to only delete a subset of all the cookies.
        """
        args: list[str] = []
        if domain is not None:
            args.append(domain)
        if path is not None:
            assert domain is not None
            args.append(path)
        self.jar.clear(*args)

    def update(self, cookies: CookieTypes | None = None) -> None:  # type: ignore
        cookies_obj = Cookies(cookies)
        for cookie in cookies_obj.jar:
            self.jar.set_cookie(cookie)

    def __setitem__(self, name: str, value: str) -> None:
        return self.set(name, value)

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __delitem__(self, name: str) -> None:
        return self.delete(name)

    def __len__(self) -> int:
        return len(self.jar)

    def __iter__(self) -> Iterator[str]:
        return (cookie.name for cookie in self.jar)

    def __bool__(self) -> bool:
        for _ in self.jar:
            return True
        return False

    def __repr__(self) -> str:
        cookies_repr = ", ".join(
            [
                f"<Cookie {cookie.name}={cookie.value} for {cookie.domain} />"
                for cookie in self.jar
            ]
        )
        return f"<Cookies[{cookies_repr}]>"

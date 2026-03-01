"""Tests for curl_cffi API compatibility."""

import pytest


class TestBaseUrl:
    """Test base_url feature."""

    def test_base_url_sync(self):
        """Test base_url with sync Session."""
        from rnet_requests import Session

        with Session(base_url="https://httpbin.org") as s:
            r = s.get("/get")
            assert r.status_code == 200
            assert "httpbin.org" in r.url

    def test_base_url_with_trailing_slash(self):
        """Test base_url with trailing slash."""
        from rnet_requests import Session

        with Session(base_url="https://httpbin.org/") as s:
            r = s.get("get")
            assert r.status_code == 200
            assert "httpbin.org/get" in r.url

    def test_base_url_absolute_url_override(self):
        """Test that absolute URLs override base_url."""
        from rnet_requests import Session

        with Session(base_url="https://example.com") as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200
            assert "httpbin.org" in r.url

    def test_base_url_invalid(self):
        """Test that relative base_url raises error."""
        from rnet_requests import Session

        with pytest.raises(ValueError, match="absolute url"):
            Session(base_url="/relative/path")

    @pytest.mark.asyncio
    async def test_base_url_async(self):
        """Test base_url with async AsyncSession."""
        from rnet_requests import AsyncSession

        async with AsyncSession(base_url="https://httpbin.org") as s:
            r = await s.get("/get")
            assert r.status_code == 200
            assert "httpbin.org" in r.url


class TestDefaultParams:
    """Test default params feature."""

    def test_default_params_sync(self):
        """Test default params with sync Session."""
        from rnet_requests import Session

        with Session(params={"key": "value"}) as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200
            data = r.json()
            assert data["args"]["key"] == "value"

    def test_default_params_merge(self):
        """Test that request params merge with default params."""
        from rnet_requests import Session

        with Session(params={"default": "value"}) as s:
            r = s.get("https://httpbin.org/get", params={"request": "param"})
            assert r.status_code == 200
            data = r.json()
            assert data["args"]["default"] == "value"
            assert data["args"]["request"] == "param"

    def test_default_params_override(self):
        """Test that request params override default params."""
        from rnet_requests import Session

        with Session(params={"key": "default"}) as s:
            r = s.get("https://httpbin.org/get", params={"key": "override"})
            assert r.status_code == 200
            data = r.json()
            assert data["args"]["key"] == "override"

    @pytest.mark.asyncio
    async def test_default_params_async(self):
        """Test default params with async AsyncSession."""
        from rnet_requests import AsyncSession

        async with AsyncSession(params={"key": "value"}) as s:
            r = await s.get("https://httpbin.org/get")
            assert r.status_code == 200
            data = r.json()
            assert data["args"]["key"] == "value"


class TestProxyParameter:
    """Test proxy parameter (single proxy shorthand)."""

    def test_proxy_parameter_error(self):
        """Test that specifying both proxy and proxies raises error."""
        from rnet_requests import Session

        with pytest.raises(TypeError, match="Cannot specify both"):
            Session(proxy="http://proxy:8080", proxies={"http": "http://other:8080"})


class TestHeaders:
    """Test Headers class."""

    def test_headers_basic(self):
        """Test basic Headers functionality."""
        from rnet_requests import Headers

        h = Headers({"Content-Type": "application/json"})
        assert h["content-type"] == "application/json"
        assert "Content-Type" in h

    def test_headers_get_list(self):
        """Test Headers.get_list method."""
        from rnet_requests import Headers

        h = Headers([("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")])
        cookies = h.get_list("set-cookie")
        assert len(cookies) == 2
        assert "a=1" in cookies
        assert "b=2" in cookies

    def test_headers_multi_items(self):
        """Test Headers.multi_items method."""
        from rnet_requests import Headers

        h = Headers([("X-Custom", "value1"), ("X-Custom", "value2")])
        items = h.multi_items()
        assert len(items) == 2

    def test_headers_case_insensitive(self):
        """Test Headers case insensitivity."""
        from rnet_requests import Headers

        h = Headers()
        h["Content-Type"] = "text/plain"
        assert h["content-type"] == "text/plain"
        assert h["CONTENT-TYPE"] == "text/plain"


class TestCookies:
    """Test Cookies class."""

    def test_cookies_basic(self):
        """Test basic Cookies functionality."""
        from rnet_requests import Cookies

        c = Cookies({"session": "abc123"})
        assert c["session"] == "abc123"
        assert "session" in c

    def test_cookies_set_with_domain(self):
        """Test Cookies.set with domain."""
        from rnet_requests import Cookies

        c = Cookies()
        c.set("name", "value", domain="example.com")
        assert c.get("name") == "value"

    def test_cookies_get_dict(self):
        """Test Cookies.get_dict method."""
        from rnet_requests import Cookies

        c = Cookies({"a": "1", "b": "2"})
        d = c.get_dict()
        assert d == {"a": "1", "b": "2"}

    def test_cookies_delete(self):
        """Test Cookies.delete method."""
        from rnet_requests import Cookies

        c = Cookies({"a": "1", "b": "2"})
        c.delete("a")
        assert "a" not in c
        assert "b" in c

    def test_cookies_clear(self):
        """Test Cookies.clear method."""
        from rnet_requests import Cookies

        c = Cookies({"a": "1", "b": "2"})
        c.clear()
        assert len(c) == 0


class TestBrowserType:
    """Test BrowserType enum."""

    def test_browser_type_values(self):
        """Test BrowserType enum values."""
        from rnet_requests import BrowserType

        assert BrowserType.chrome.value == "chrome"
        assert BrowserType.firefox.value == "firefox"
        assert BrowserType.safari.value == "safari"

    def test_browser_type_with_session(self):
        """Test using BrowserType with Session."""
        from rnet_requests import BrowserType, Session

        with Session(impersonate=BrowserType.chrome) as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200


class TestMultipart:
    """Test Multipart form data."""

    def test_multipart_basic(self):
        """Test basic Multipart creation."""
        from rnet_requests import Multipart

        mp = Multipart()
        mp.addpart("field", data=b"value")
        assert len(mp) == 1

    def test_multipart_with_file(self):
        """Test Multipart with file data."""
        from rnet_requests import Multipart

        mp = Multipart()
        mp.addpart("file", filename="test.txt", data=b"Hello, World!")
        assert len(mp) == 1

    def test_multipart_from_dict(self):
        """Test Multipart.from_dict method."""
        from rnet_requests import Multipart

        mp = Multipart.from_dict(
            {
                "field": "value",
                "file": ("test.txt", b"content", "text/plain"),
            }
        )
        assert len(mp) == 2

    def test_multipart_upload_sync(self):
        """Test uploading with Multipart (sync)."""
        from rnet_requests import Multipart, Session

        mp = Multipart()
        mp.addpart("file", filename="test.txt", data=b"Hello from Multipart!")
        mp.addpart("field", data=b"extra_value")

        with Session() as s:
            r = s.post("https://httpbin.org/post", multipart=mp)
            assert r.status_code == 200
            data = r.json()
            assert "file" in data["files"]
            assert "Hello from Multipart!" in data["files"]["file"]
            assert data["form"]["field"] == "extra_value"

    @pytest.mark.asyncio
    async def test_multipart_upload_async(self):
        """Test uploading with Multipart (async)."""
        from rnet_requests import AsyncSession, Multipart

        mp = Multipart()
        mp.addpart("document", filename="doc.txt", data=b"Async multipart content")

        async with AsyncSession() as s:
            r = await s.post("https://httpbin.org/post", multipart=mp)
            assert r.status_code == 200
            data = r.json()
            assert "document" in data["files"]

    def test_multipart_from_dict_upload(self):
        """Test uploading with Multipart.from_dict."""
        from rnet_requests import Multipart, Session

        mp = Multipart.from_dict(
            {
                "text_field": "just text",
                "binary_field": b"binary data",
                "file_field": ("upload.txt", b"file content", "text/plain"),
            }
        )

        with Session() as s:
            r = s.post("https://httpbin.org/post", multipart=mp)
            assert r.status_code == 200
            data = r.json()
            assert data["form"]["text_field"] == "just text"
            assert "file_field" in data["files"]

    def test_multipart_with_content_type(self):
        """Test Multipart with custom content type."""
        from rnet_requests import Multipart

        mp = Multipart()
        mp.addpart(
            "image", filename="test.png", data=b"\x89PNG", content_type="image/png"
        )
        assert len(mp) == 1


class TestInitialCookies:
    """Test initial cookies parameter."""

    def test_initial_cookies_sync(self):
        """Test initial cookies with sync Session."""
        from rnet_requests import Session

        with Session(cookies={"preset": "value"}) as s:
            assert s.cookies["preset"] == "value"
            r = s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["preset"] == "value"

    @pytest.mark.asyncio
    async def test_initial_cookies_async(self):
        """Test initial cookies with async AsyncSession."""
        from rnet_requests import AsyncSession

        async with AsyncSession(cookies={"preset": "value"}) as s:
            assert s.cookies["preset"] == "value"
            r = await s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["preset"] == "value"


class TestResponseHistory:
    """Test response.history for redirect tracking."""

    def test_history_populated_on_redirect(self):
        """Test that history is populated on redirects."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/redirect/3")
            assert r.status_code == 200
            assert len(r.history) == 3
            # Each history entry should be a Response
            for h in r.history:
                assert h.status_code == 302
                assert h.url is not None
                assert h.reason == "Found"

    def test_history_empty_no_redirect(self):
        """Test that history is empty when no redirects."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200
            assert len(r.history) == 0

    def test_history_has_headers(self):
        """Test that history entries have headers."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/redirect/1")
            assert len(r.history) == 1
            # History entry should have headers
            assert (
                "location" in r.history[0].headers or "Location" in r.history[0].headers
            )

    @pytest.mark.asyncio
    async def test_history_async(self):
        """Test history with async session."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/redirect/2")
            assert r.status_code == 200
            assert len(r.history) == 2
            for h in r.history:
                assert h.status_code == 302

    def test_history_url_chain(self):
        """Test that history URLs form correct chain."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/redirect/2")
            assert len(r.history) == 2
            # URLs should show the redirect chain
            assert (
                "redirect" in r.history[0].url
                or "relative-redirect" in r.history[0].url
            )


class TestResponseElapsed:
    """Test response.elapsed timing."""

    def test_elapsed_is_timedelta(self):
        """Test that elapsed is a timedelta."""
        from datetime import timedelta

        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/get")
            assert isinstance(r.elapsed, timedelta)

    def test_elapsed_positive(self):
        """Test that elapsed is positive."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/get")
            assert r.elapsed.total_seconds() > 0

    def test_elapsed_delay_request(self):
        """Test elapsed with delayed response."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/delay/1")
            # Should be at least 1 second
            assert r.elapsed.total_seconds() >= 1.0

    @pytest.mark.asyncio
    async def test_elapsed_async(self):
        """Test elapsed with async session."""
        from datetime import timedelta

        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/get")
            assert isinstance(r.elapsed, timedelta)
            assert r.elapsed.total_seconds() > 0


class TestCookiesClass:
    """Test that session and response cookies are Cookies class."""

    def test_session_cookies_is_cookies_class(self):
        """Test that session.cookies is Cookies class."""
        from rnet_requests import Cookies, Session

        with Session() as s:
            assert isinstance(s.cookies, Cookies)

    def test_response_cookies_is_cookies_class(self):
        """Test that response.cookies is Cookies class."""
        from rnet_requests import Cookies, Session

        with Session() as s:
            r = s.get("https://httpbin.org/cookies/set/testcookie/testvalue")
            assert isinstance(r.cookies, Cookies)

    def test_session_cookies_set_with_domain(self):
        """Test setting cookies with domain on session."""
        from rnet_requests import Session

        with Session() as s:
            s.cookies.set("name", "value", domain=".example.com")
            assert s.cookies.get("name") == "value"

    def test_response_cookies_get_with_domain(self):
        """Test getting cookies with domain from response."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/cookies/set/testcookie/testvalue")
            # Should be able to call get with domain parameter
            value = r.cookies.get("testcookie")
            assert value == "testvalue"

    @pytest.mark.asyncio
    async def test_async_session_cookies_class(self):
        """Test async session cookies is Cookies class."""
        from rnet_requests import AsyncSession, Cookies

        async with AsyncSession() as s:
            assert isinstance(s.cookies, Cookies)
            s.cookies.set("test", "value", domain=".example.com")
            assert s.cookies.get("test") == "value"


class TestMultipartFromList:
    """Test Multipart.from_list() method for CurlMime compatibility."""

    def test_from_list_basic(self):
        """Test basic from_list functionality."""
        from rnet_requests import Multipart

        mp = Multipart.from_list(
            [
                {"name": "field1", "data": "value1"},
                {"name": "field2", "data": b"value2"},
            ]
        )
        assert len(mp) == 2

    def test_from_list_with_filename(self):
        """Test from_list with filename."""
        from rnet_requests import Multipart

        mp = Multipart.from_list(
            [
                {"name": "file", "filename": "test.txt", "data": b"content"},
            ]
        )
        assert len(mp) == 1

    def test_from_list_with_content_type(self):
        """Test from_list with content_type."""
        from rnet_requests import Multipart

        mp = Multipart.from_list(
            [
                {
                    "name": "image",
                    "filename": "test.png",
                    "data": b"\x89PNG",
                    "content_type": "image/png",
                },
            ]
        )
        assert len(mp) == 1

    def test_from_list_missing_name_raises(self):
        """Test that from_list raises error if name missing."""
        from rnet_requests import Multipart

        with pytest.raises(ValueError, match="name"):
            Multipart.from_list([{"data": "value"}])

    def test_from_list_upload(self):
        """Test uploading with from_list."""
        from rnet_requests import Multipart, Session

        mp = Multipart.from_list(
            [
                {"name": "text", "data": "hello"},
                {"name": "file", "filename": "test.txt", "data": b"file content"},
            ]
        )

        with Session() as s:
            r = s.post("https://httpbin.org/post", multipart=mp)
            assert r.status_code == 200
            data = r.json()
            assert data["form"]["text"] == "hello"
            assert "file" in data["files"]


class TestSyncWebSocketError:
    """Test that sync Session.ws_connect raises helpful error."""

    def test_ws_connect_raises_not_implemented(self):
        """Test that sync ws_connect raises NotImplementedError."""
        from rnet_requests import Session

        with Session() as s, pytest.raises(NotImplementedError, match="AsyncSession"):
            s.ws_connect("wss://echo.websocket.org")


class TestOSImpersonation:
    """Test OS impersonation feature."""

    def test_impersonate_os_windows(self):
        """Test Windows OS impersonation."""
        from rnet_requests import Session

        with Session(impersonate="chrome", impersonate_os="windows") as s:
            r = s.get("https://httpbin.org/headers")
            assert r.status_code == 200
            ua = r.json()["headers"].get("User-Agent", "")
            assert "Windows" in ua

    def test_impersonate_os_macos(self):
        """Test macOS impersonation."""
        from rnet_requests import Session

        with Session(impersonate="chrome", impersonate_os="macos") as s:
            r = s.get("https://httpbin.org/headers")
            assert r.status_code == 200
            ua = r.json()["headers"].get("User-Agent", "")
            assert "Mac" in ua or "Macintosh" in ua

    def test_impersonate_os_linux(self):
        """Test Linux OS impersonation."""
        from rnet_requests import Session

        with Session(impersonate="chrome", impersonate_os="linux") as s:
            r = s.get("https://httpbin.org/headers")
            assert r.status_code == 200
            ua = r.json()["headers"].get("User-Agent", "")
            assert "Linux" in ua

    @pytest.mark.asyncio
    async def test_impersonate_os_async(self):
        """Test OS impersonation with async session."""
        from rnet_requests import AsyncSession

        async with AsyncSession(impersonate="firefox", impersonate_os="windows") as s:
            r = await s.get("https://httpbin.org/headers")
            assert r.status_code == 200
            ua = r.json()["headers"].get("User-Agent", "")
            assert "Windows" in ua


class TestModuleLevelOSImpersonation:
    """Test OS impersonation with module-level functions."""

    def test_module_level_get_with_impersonate_os(self):
        """Test module-level get() with impersonate_os."""
        import rnet_requests

        r = rnet_requests.get(
            "https://httpbin.org/headers",
            impersonate="chrome",
            impersonate_os="windows",
        )
        assert r.status_code == 200
        ua = r.json()["headers"].get("User-Agent", "")
        assert "Windows" in ua

    def test_module_level_request_with_impersonate_os(self):
        """Test module-level request() with impersonate_os."""
        import rnet_requests

        r = rnet_requests.request(
            "GET",
            "https://httpbin.org/headers",
            impersonate="firefox",
            impersonate_os="macos",
        )
        assert r.status_code == 200
        ua = r.json()["headers"].get("User-Agent", "")
        assert "Mac" in ua or "Macintosh" in ua

    @pytest.mark.asyncio
    async def test_async_module_level_get_with_impersonate_os(self):
        """Test async module-level get() with impersonate_os."""
        import rnet_requests

        r = await rnet_requests.async_get(
            "https://httpbin.org/headers",
            impersonate="chrome",
            impersonate_os="linux",
        )
        assert r.status_code == 200
        ua = r.json()["headers"].get("User-Agent", "")
        assert "Linux" in ua


class TestSessionClosed:
    """Test SessionClosed exception."""

    def test_sync_session_closed_raises(self):
        """Test that using closed sync session raises SessionClosed."""
        from rnet_requests import Session
        from rnet_requests.exceptions import SessionClosed

        s = Session()
        s.close()
        with pytest.raises(SessionClosed):
            s.get("https://httpbin.org/get")

    @pytest.mark.asyncio
    async def test_async_session_closed_raises(self):
        """Test that using closed async session raises SessionClosed."""
        from rnet_requests import AsyncSession
        from rnet_requests.exceptions import SessionClosed

        s = AsyncSession()
        await s.close()
        with pytest.raises(SessionClosed):
            await s.get("https://httpbin.org/get")


class TestRetryStrategy:
    """Test retry functionality."""

    def test_retry_strategy_creation(self):
        """Test RetryStrategy dataclass."""
        from rnet_requests import RetryStrategy

        strategy = RetryStrategy(count=3, delay=1.0, jitter=0.5, backoff="exponential")
        assert strategy.count == 3
        assert strategy.delay == 1.0
        assert strategy.jitter == 0.5
        assert strategy.backoff == "exponential"

    def test_retry_strategy_defaults(self):
        """Test RetryStrategy default values."""
        from rnet_requests import RetryStrategy

        strategy = RetryStrategy(count=2)
        assert strategy.count == 2
        assert strategy.delay == 0.0
        assert strategy.jitter == 0.0
        assert strategy.backoff == "linear"

    def test_session_with_retry_int(self):
        """Test Session with retry as int."""
        from rnet_requests import Session

        with Session(retry=3) as s:
            assert s.retry.count == 3
            assert s.retry.delay == 0.0

    def test_session_with_retry_strategy(self):
        """Test Session with RetryStrategy."""
        from rnet_requests import RetryStrategy, Session

        strategy = RetryStrategy(count=2, delay=0.5)
        with Session(retry=strategy) as s:
            assert s.retry.count == 2
            assert s.retry.delay == 0.5

    @pytest.mark.asyncio
    async def test_async_session_with_retry(self):
        """Test AsyncSession with retry."""
        from rnet_requests import AsyncSession, RetryStrategy

        strategy = RetryStrategy(count=2, delay=0.1)
        async with AsyncSession(retry=strategy) as s:
            assert s.retry.count == 2
            r = await s.get("https://httpbin.org/get")
            assert r.status_code == 200


class TestRefererShortcut:
    """Test referer parameter shortcut."""

    def test_referer_sync(self):
        """Test referer shortcut in sync request."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/headers", referer="https://example.com")
            assert r.status_code == 200
            headers = r.json()["headers"]
            assert headers.get("Referer") == "https://example.com"

    @pytest.mark.asyncio
    async def test_referer_async(self):
        """Test referer shortcut in async request."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/headers", referer="https://test.com")
            assert r.status_code == 200
            headers = r.json()["headers"]
            assert headers.get("Referer") == "https://test.com"


class TestRaiseForStatus:
    """Test raise_for_status parameter."""

    def test_raise_for_status_disabled(self):
        """Test that 4xx doesn't raise when raise_for_status=False."""
        from rnet_requests import Session

        with Session(raise_for_status=False) as s:
            r = s.get("https://httpbin.org/status/404")
            assert r.status_code == 404

    def test_raise_for_status_enabled(self):
        """Test that 4xx raises when raise_for_status=True."""
        from rnet_requests import Session
        from rnet_requests.exceptions import HTTPError

        with Session(raise_for_status=True) as s, pytest.raises(HTTPError):
            s.get("https://httpbin.org/status/404")

    @pytest.mark.asyncio
    async def test_raise_for_status_async(self):
        """Test raise_for_status with async session."""
        from rnet_requests import AsyncSession
        from rnet_requests.exceptions import HTTPError

        async with AsyncSession(raise_for_status=True) as s:
            with pytest.raises(HTTPError):
                await s.get("https://httpbin.org/status/500")


class TestDefaultEncoding:
    """Test default_encoding parameter."""

    def test_default_encoding_session(self):
        """Test default_encoding in Session."""
        from rnet_requests import Session

        with Session(default_encoding="latin-1") as s:
            assert s.default_encoding == "latin-1"
            r = s.get("https://httpbin.org/get")
            assert r.default_encoding == "latin-1"

    def test_default_encoding_callable(self):
        """Test default_encoding with callable."""
        from rnet_requests import Session

        def detect_encoding(content: bytes) -> str:
            return "utf-8"

        with Session(default_encoding=detect_encoding) as s:
            assert callable(s.default_encoding)


class TestDiscardCookies:
    """Test discard_cookies parameter."""

    def test_discard_cookies_session(self):
        """Test discard_cookies at session level."""
        from rnet_requests import Session

        with Session(discard_cookies=True) as s:
            s.get("https://httpbin.org/cookies/set/foo/bar")
            # Session shouldn't store the cookie
            assert len(s.cookies) == 0

    def test_discard_cookies_request(self):
        """Test discard_cookies at request level."""
        from rnet_requests import Session

        with Session() as s:
            s.get(
                "https://httpbin.org/cookies/set/test/value",
                discard_cookies=True,
            )
            # Cookie shouldn't be stored
            assert "test" not in s.cookies


class TestHttpVersion:
    """Test http_version parameter."""

    def test_http_version_string(self):
        """Test http_version with string value."""
        from rnet_requests import Session

        # Just test it doesn't error - we can't easily verify the HTTP version used
        with Session(http_version="HTTP/2") as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200


class TestDebugMode:
    """Test debug parameter."""

    def test_debug_mode(self):
        """Test Session with debug=True."""
        from rnet_requests import Session

        # Just test it doesn't error
        with Session(debug=True) as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200


class TestDefaultHeaders:
    """Test default_headers parameter."""

    def test_default_headers_enabled(self):
        """Test with default_headers=True (default)."""
        from rnet_requests import Session

        with Session(impersonate="chrome", default_headers=True) as s:
            r = s.get("https://httpbin.org/headers")
            assert r.status_code == 200

    def test_default_headers_disabled(self):
        """Test with default_headers=False."""
        from rnet_requests import Session

        with Session(default_headers=False) as s:
            r = s.get("https://httpbin.org/headers")
            assert r.status_code == 200


class TestStreaming:
    """Test response streaming support."""

    def test_stream_iter_content(self):
        """Test stream=True with iter_content()."""
        from rnet_requests import Session

        with Session() as s:
            # Request 1KB of random bytes
            r = s.get("https://httpbin.org/bytes/1024", stream=True)
            assert r.status_code == 200

            chunks = list(r.iter_content(chunk_size=256))
            total_bytes = sum(len(chunk) for chunk in chunks)
            assert total_bytes == 1024

    def test_stream_iter_lines(self):
        """Test stream=True with iter_lines()."""
        from rnet_requests import Session

        with Session() as s:
            # Request 10 lines of data
            r = s.get("https://httpbin.org/stream/10", stream=True)
            assert r.status_code == 200

            lines = list(r.iter_lines())
            # Should have at least 10 lines (may have more due to chunking)
            assert len(lines) >= 10

    def test_stream_content_property_consumes(self):
        """Test that accessing .content on stream consumes it."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/bytes/512", stream=True)
            assert r.status_code == 200
            assert r._is_stream is True
            assert r._stream_consumed is False

            # Accessing content should consume the stream
            content = r.content
            assert len(content) == 512
            assert r._stream_consumed is True

    def test_non_stream_iter_content(self):
        """Test iter_content() without stream=True."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/bytes/256")
            assert r.status_code == 200
            assert r._is_stream is False

            chunks = list(r.iter_content(chunk_size=64))
            total_bytes = sum(len(chunk) for chunk in chunks)
            assert total_bytes == 256

    @pytest.mark.asyncio
    async def test_async_stream_aiter_content(self):
        """Test async stream=True with aiter_content()."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/bytes/1024", stream=True)
            assert r.status_code == 200

            chunks = []
            async for chunk in r.aiter_content(chunk_size=256):
                chunks.append(chunk)

            total_bytes = sum(len(chunk) for chunk in chunks)
            assert total_bytes == 1024

    @pytest.mark.asyncio
    async def test_async_stream_aiter_lines(self):
        """Test async stream=True with aiter_lines()."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/stream/10", stream=True)
            assert r.status_code == 200

            lines = []
            async for line in r.aiter_lines():
                lines.append(line)

            # Should have at least 10 lines
            assert len(lines) >= 10

    @pytest.mark.asyncio
    async def test_async_stream_atext(self):
        """Test async atext() method for streaming."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/get", stream=True)
            assert r.status_code == 200

            text = await r.atext()
            assert "httpbin.org" in text

    @pytest.mark.asyncio
    async def test_async_stream_acontent(self):
        """Test async acontent() method for streaming."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/bytes/256", stream=True)
            assert r.status_code == 200

            content = await r.acontent()
            assert len(content) == 256

    def test_stream_close(self):
        """Test close() on streaming response."""
        from rnet_requests import Session

        with Session() as s:
            r = s.get("https://httpbin.org/bytes/1024", stream=True)
            assert r.status_code == 200

            # Close without consuming
            r.close()
            assert r._stream_consumed is True

    def test_stream_context_manager(self):
        """Test streaming response as context manager."""
        from rnet_requests import Session

        with Session() as s, s.get("https://httpbin.org/bytes/512", stream=True) as r:
            assert r.status_code == 200
            chunks = list(r.iter_content())
            total_bytes = sum(len(chunk) for chunk in chunks)
            assert total_bytes == 512

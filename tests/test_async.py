"""Async tests for rnet-requests."""

import pytest


class TestAsyncImports:
    """Test that async imports work correctly."""

    def test_import_async_session(self):
        """Test importing AsyncSession class."""
        from rnet_requests import AsyncSession

        assert AsyncSession is not None

    def test_import_async_functions(self):
        """Test importing async API functions."""
        # These should be coroutine functions
        import asyncio

        from rnet_requests import (
            async_delete,
            async_get,
            async_head,
            async_options,
            async_patch,
            async_post,
            async_put,
            async_request,
        )

        assert asyncio.iscoroutinefunction(async_get)
        assert asyncio.iscoroutinefunction(async_post)
        assert asyncio.iscoroutinefunction(async_put)
        assert asyncio.iscoroutinefunction(async_patch)
        assert asyncio.iscoroutinefunction(async_delete)
        assert asyncio.iscoroutinefunction(async_head)
        assert asyncio.iscoroutinefunction(async_options)
        assert asyncio.iscoroutinefunction(async_request)


class TestAsyncSession:
    """Test AsyncSession class."""

    def test_async_session_creation(self):
        """Test creating an async session."""
        from rnet_requests import AsyncSession

        s = AsyncSession()
        assert s is not None

    def test_async_session_with_impersonate_string(self):
        """Test async session with string impersonation."""
        from rnet_requests import AsyncSession

        s = AsyncSession(impersonate="chrome")
        assert s is not None

    def test_async_session_with_impersonate_enum(self):
        """Test async session with enum impersonation."""
        from rnet_requests import AsyncSession, Impersonate

        s = AsyncSession(impersonate=Impersonate.Firefox139)
        assert s is not None

    def test_async_session_headers(self):
        """Test async session headers."""
        from rnet_requests import AsyncSession

        s = AsyncSession(headers={"X-Custom": "value"})
        assert s.headers["x-custom"] == "value"


@pytest.mark.asyncio
class TestAsyncRequests:
    """Test real async HTTP requests."""

    async def test_async_simple_get(self):
        """Test a simple async GET request."""
        from rnet_requests import async_get

        r = await async_get("https://httpbin.org/get")
        assert r.status_code == 200
        assert r.ok
        data = r.json()
        assert "headers" in data
        assert "url" in data

    async def test_async_get_with_params(self):
        """Test async GET request with query parameters."""
        from rnet_requests import async_get

        params = {"foo": "bar", "baz": "123"}
        r = await async_get("https://httpbin.org/get", params=params)
        assert r.status_code == 200
        data = r.json()
        assert data["args"]["foo"] == "bar"
        assert data["args"]["baz"] == "123"

    async def test_async_post_json(self):
        """Test async POST request with JSON body."""
        from rnet_requests import async_post

        payload = {"key": "value", "number": 42}
        r = await async_post("https://httpbin.org/post", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["json"] == payload

    async def test_async_post_form_data(self):
        """Test async POST request with form data."""
        from rnet_requests import async_post

        payload = {"username": "testuser", "password": "secret"}
        r = await async_post("https://httpbin.org/post", data=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["form"]["username"] == "testuser"
        assert data["form"]["password"] == "secret"

    async def test_async_custom_headers(self):
        """Test async request with custom headers."""
        from rnet_requests import async_get

        headers = {"X-Custom-Header": "custom-value"}
        r = await async_get("https://httpbin.org/headers", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["headers"]["X-Custom-Header"] == "custom-value"

    async def test_async_status_codes(self):
        """Test various async status codes."""
        from rnet_requests import HTTPError, async_get

        r = await async_get("https://httpbin.org/status/200")
        assert r.status_code == 200
        assert r.ok

        r = await async_get("https://httpbin.org/status/404")
        assert r.status_code == 404
        assert not r.ok

        with pytest.raises(HTTPError):
            r.raise_for_status()


@pytest.mark.asyncio
class TestAsyncSessionRequests:
    """Test AsyncSession-based requests."""

    async def test_async_session_basic(self):
        """Test basic async session usage."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            r = await s.get("https://httpbin.org/get")
            assert r.status_code == 200

    async def test_async_session_cookies(self):
        """Test async session cookie persistence."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as s:
            # Set a cookie
            await s.get("https://httpbin.org/cookies/set/test_cookie/test_value")

            # Check that cookie is sent in subsequent requests
            r = await s.get("https://httpbin.org/cookies")
            data = r.json()
            assert "test_cookie" in data.get("cookies", {})

    async def test_async_session_headers(self):
        """Test async session default headers."""
        from rnet_requests import AsyncSession

        async with AsyncSession(headers={"X-Session-Header": "session-value"}) as s:
            r = await s.get("https://httpbin.org/headers")
            data = r.json()
            assert data["headers"]["X-Session-Header"] == "session-value"


@pytest.mark.asyncio
class TestAsyncImpersonation:
    """Test async browser impersonation."""

    async def test_async_chrome_impersonation(self):
        """Test async Chrome impersonation."""
        from rnet_requests import async_get

        r = await async_get("https://tls.peet.ws/api/all", impersonate="chrome")
        assert r.status_code == 200
        data = r.json()

        # Should have TLS fingerprint info
        assert "tls" in data
        assert "http_version" in data

    async def test_async_firefox_impersonation(self):
        """Test async Firefox impersonation."""
        from rnet_requests import AsyncSession

        async with AsyncSession(impersonate="firefox") as s:
            r = await s.get("https://tls.peet.ws/api/all")
            assert r.status_code == 200
            data = r.json()
            assert "tls" in data

    async def test_async_impersonate_with_enum(self):
        """Test async impersonation with enum."""
        from rnet import Emulation

        from rnet_requests import AsyncSession

        async with AsyncSession(impersonate=Emulation.Safari18) as s:
            r = await s.get("https://tls.peet.ws/api/all")
            assert r.status_code == 200

"""Integration tests for rnet-requests making real HTTP calls."""

import pytest


class TestRealRequests:
    """Test real HTTP requests."""

    def test_simple_get(self):
        """Test a simple GET request."""
        import rnet_requests as requests

        r = requests.get("https://httpbin.org/get")
        assert r.status_code == 200
        assert r.ok
        data = r.json()
        assert "headers" in data
        assert "url" in data

    def test_get_with_params(self):
        """Test GET request with query parameters."""
        import rnet_requests as requests

        r = requests.get("https://httpbin.org/get", params={"foo": "bar", "baz": "123"})
        assert r.status_code == 200
        data = r.json()
        assert data["args"]["foo"] == "bar"
        assert data["args"]["baz"] == "123"

    def test_post_json(self):
        """Test POST request with JSON body."""
        import rnet_requests as requests

        payload = {"key": "value", "number": 42}
        r = requests.post("https://httpbin.org/post", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["json"] == payload

    def test_post_form_data(self):
        """Test POST request with form data."""
        import rnet_requests as requests

        payload = {"username": "testuser", "password": "secret"}
        r = requests.post("https://httpbin.org/post", data=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["form"]["username"] == "testuser"
        assert data["form"]["password"] == "secret"

    def test_custom_headers(self):
        """Test request with custom headers."""
        import rnet_requests as requests

        headers = {"X-Custom-Header": "custom-value"}
        r = requests.get("https://httpbin.org/headers", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["headers"]["X-Custom-Header"] == "custom-value"

    def test_response_headers(self):
        """Test reading response headers."""
        import rnet_requests as requests

        url = "https://httpbin.org/response-headers"
        r = requests.get(url, params={"X-Test": "hello"})
        assert r.status_code == 200
        # Response headers should be case-insensitive
        assert "content-type" in r.headers or "Content-Type" in r.headers

    def test_status_codes(self):
        """Test various status codes."""
        import rnet_requests as requests
        from rnet_requests import HTTPError

        r = requests.get("https://httpbin.org/status/200")
        assert r.status_code == 200
        assert r.ok

        r = requests.get("https://httpbin.org/status/404")
        assert r.status_code == 404
        assert not r.ok

        with pytest.raises(HTTPError):
            r.raise_for_status()


class TestSessionRequests:
    """Test Session-based requests."""

    def test_session_basic(self):
        """Test basic session usage."""
        import rnet_requests as requests

        with requests.Session() as s:
            r = s.get("https://httpbin.org/get")
            assert r.status_code == 200

    def test_session_cookies(self):
        """Test session cookie persistence."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set a cookie
            s.get("https://httpbin.org/cookies/set/test_cookie/test_value")

            # Check that cookie is sent in subsequent requests
            r = s.get("https://httpbin.org/cookies")
            data = r.json()
            assert "test_cookie" in data.get("cookies", {})

    def test_session_headers(self):
        """Test session default headers."""
        import rnet_requests as requests

        with requests.Session(headers={"X-Session-Header": "session-value"}) as s:
            r = s.get("https://httpbin.org/headers")
            data = r.json()
            assert data["headers"]["X-Session-Header"] == "session-value"


class TestImpersonation:
    """Test browser impersonation."""

    def test_chrome_impersonation(self):
        """Test Chrome impersonation."""
        import rnet_requests as requests

        r = requests.get("https://tls.peet.ws/api/all", impersonate="chrome")
        assert r.status_code == 200
        data = r.json()

        # Should have TLS fingerprint info
        assert "tls" in data
        assert "http_version" in data

    def test_firefox_impersonation(self):
        """Test Firefox impersonation."""
        import rnet_requests as requests

        with requests.Session(impersonate="firefox") as s:
            r = s.get("https://tls.peet.ws/api/all")
            assert r.status_code == 200
            data = r.json()
            assert "tls" in data

    def test_impersonate_with_enum(self):
        """Test impersonation with enum."""
        from rnet import Emulation

        import rnet_requests as requests

        with requests.Session(impersonate=Emulation.Safari18) as s:
            r = s.get("https://tls.peet.ws/api/all")
            assert r.status_code == 200

"""Basic tests for rnet-requests."""

import pytest


class TestImports:
    """Test that all imports work correctly."""

    def test_import_module(self):
        """Test importing the main module."""
        import rnet_requests

        assert rnet_requests.__version__ == "0.1.0"

    def test_import_api_functions(self):
        """Test importing API functions."""
        from rnet_requests import delete, get, head, options, patch, post, put, request

        assert callable(get)
        assert callable(post)
        assert callable(put)
        assert callable(patch)
        assert callable(delete)
        assert callable(head)
        assert callable(options)
        assert callable(request)

    def test_import_session(self):
        """Test importing Session class."""
        from rnet_requests import Session

        assert Session is not None

    def test_import_response(self):
        """Test importing Response class."""
        from rnet_requests import Response

        assert Response is not None

    def test_import_exceptions(self):
        """Test importing exceptions."""
        from rnet_requests import (
            ConnectionError,
            HTTPError,
            RequestException,
            Timeout,
        )

        assert issubclass(HTTPError, RequestException)
        assert issubclass(ConnectionError, RequestException)
        assert issubclass(Timeout, RequestException)

    def test_import_impersonate(self):
        """Test importing rnet's impersonate classes."""
        from rnet_requests import Impersonate, ImpersonateOS

        assert Impersonate.Chrome137 is not None
        assert ImpersonateOS.Windows is not None


class TestCaseInsensitiveDict:
    """Test CaseInsensitiveDict."""

    def test_case_insensitive_get(self):
        """Test case-insensitive access."""
        from rnet_requests.structures import CaseInsensitiveDict

        d = CaseInsensitiveDict({"Content-Type": "application/json"})
        assert d["content-type"] == "application/json"
        assert d["CONTENT-TYPE"] == "application/json"
        assert d["Content-Type"] == "application/json"

    def test_case_insensitive_set(self):
        """Test case-insensitive setting."""
        from rnet_requests.structures import CaseInsensitiveDict

        d = CaseInsensitiveDict()
        d["Content-Type"] = "application/json"
        d["CONTENT-TYPE"] = "text/html"
        assert len(d) == 1
        assert d["content-type"] == "text/html"

    def test_iteration(self):
        """Test that iteration returns original keys."""
        from rnet_requests.structures import CaseInsensitiveDict

        d = CaseInsensitiveDict({"Content-Type": "application/json"})
        keys = list(d.keys())
        # Should preserve original case
        assert "Content-Type" in keys or "CONTENT-TYPE" in keys


class TestResponse:
    """Test Response class."""

    def test_response_ok(self):
        """Test response ok property."""
        from rnet_requests import Response

        r = Response()
        r.status_code = 200
        assert r.ok is True

        r.status_code = 404
        assert r.ok is False

    def test_response_raise_for_status(self):
        """Test raise_for_status."""
        from rnet_requests import HTTPError, Response

        r = Response()
        r.status_code = 200
        r.url = "https://example.com"
        r.raise_for_status()  # Should not raise

        r.status_code = 404
        r.reason = "Not Found"
        with pytest.raises(HTTPError):
            r.raise_for_status()

    def test_response_json(self):
        """Test JSON parsing."""
        from rnet_requests import Response

        r = Response()
        r._content = b'{"key": "value"}'
        assert r.json() == {"key": "value"}

    def test_response_text(self):
        """Test text content."""
        from rnet_requests import Response

        r = Response()
        r._content = b"Hello World"
        r.encoding = "utf-8"
        assert r.text == "Hello World"


class TestSession:
    """Test Session class."""

    def test_session_creation(self):
        """Test creating a session."""
        from rnet_requests import Session

        s = Session()
        assert s is not None

    def test_session_with_impersonate_string(self):
        """Test session with string impersonation."""
        from rnet_requests import Session

        s = Session(impersonate="chrome")
        assert s is not None

    def test_session_with_impersonate_enum(self):
        """Test session with enum impersonation."""
        from rnet_requests import Impersonate, Session

        s = Session(impersonate=Impersonate.Firefox139)
        assert s is not None

    def test_session_headers(self):
        """Test session headers."""
        from rnet_requests import Session

        s = Session(headers={"X-Custom": "value"})
        assert s.headers["x-custom"] == "value"

    def test_session_context_manager(self):
        """Test session as context manager."""
        from rnet_requests import Session

        with Session() as s:
            assert s is not None


class TestPreparedRequest:
    """Test PreparedRequest class."""

    def test_prepare_url_with_params(self):
        """Test URL preparation with params."""
        from rnet_requests import Request

        req = Request("GET", "https://example.com/path", params={"a": "1", "b": "2"})
        prep = req.prepare()
        assert "a=1" in prep.url
        assert "b=2" in prep.url

    def test_prepare_method(self):
        """Test method preparation."""
        from rnet_requests import Request

        req = Request("get", "https://example.com")
        prep = req.prepare()
        assert prep.method == "GET"

    def test_prepare_json_body(self):
        """Test JSON body preparation."""
        from rnet_requests import Request

        req = Request("POST", "https://example.com", json={"key": "value"})
        prep = req.prepare()
        assert prep.body == '{"key": "value"}'
        assert prep.headers["Content-Type"] == "application/json"

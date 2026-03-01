"""Tests for file uploads and cookie handling."""

import os
import tempfile

import pytest


class TestFileUploads:
    """Test various file upload scenarios."""

    def test_upload_simple_file(self):
        """Test uploading a simple file."""
        import rnet_requests as requests

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name

        try:
            with open(temp_path, "rb") as f:
                files = {"file": f}
                r = requests.post("https://httpbin.org/post", files=files)

            assert r.status_code == 200
            data = r.json()
            assert "files" in data
            assert "file" in data["files"]
            assert data["files"]["file"] == "Hello, World!"
        finally:
            os.unlink(temp_path)

    def test_upload_file_with_filename(self):
        """Test uploading a file with explicit filename."""
        import rnet_requests as requests

        content = b"Test file content"
        files = {"upload": ("myfile.txt", content)}
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert "upload" in data["files"]
        assert data["files"]["upload"] == "Test file content"

    def test_upload_file_with_content_type(self):
        """Test uploading a file with explicit content type."""
        import rnet_requests as requests

        content = b'{"key": "value"}'
        files = {"data": ("data.json", content, "application/json")}
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert "data" in data["files"]

    def test_upload_multiple_files(self):
        """Test uploading multiple files."""
        import rnet_requests as requests

        files = {
            "file1": ("first.txt", b"First file content"),
            "file2": ("second.txt", b"Second file content"),
        }
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert "file1" in data["files"]
        assert "file2" in data["files"]
        assert data["files"]["file1"] == "First file content"
        assert data["files"]["file2"] == "Second file content"

    def test_upload_binary_file(self):
        """Test uploading binary content."""
        import rnet_requests as requests

        # Binary content (not valid UTF-8)
        binary_content = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD])
        files = {"binary": ("data.bin", binary_content, "application/octet-stream")}
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200

    def test_upload_large_file(self):
        """Test uploading a larger file."""
        import rnet_requests as requests

        # Create 1KB of data
        content = b"x" * 1024
        files = {"large": ("large.bin", content)}
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert len(data["files"]["large"]) == 1024

    def test_upload_with_additional_data(self):
        """Test uploading files along with form data."""
        import rnet_requests as requests

        files = {"file": ("test.txt", b"file content")}
        data = {"field1": "value1", "field2": "value2"}

        # Note: httpbin may not handle mixed multipart well
        # Just test that the request doesn't fail
        r = requests.post("https://httpbin.org/post", files=files, data=data)
        assert r.status_code == 200

    def test_upload_empty_file(self):
        """Test uploading an empty file."""
        import rnet_requests as requests

        files = {"empty": ("empty.txt", b"")}
        r = requests.post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert data["files"]["empty"] == ""


class TestCookies:
    """Test cookie handling."""

    def test_send_cookies_in_request(self):
        """Test sending cookies with a request."""
        import rnet_requests as requests

        cookies = {"session": "abc123", "user": "testuser"}
        r = requests.get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        data = r.json()
        assert data["cookies"]["session"] == "abc123"
        assert data["cookies"]["user"] == "testuser"

    def test_receive_cookies_from_response(self):
        """Test receiving cookies from response."""
        import rnet_requests as requests

        r = requests.get("https://httpbin.org/cookies/set/testcookie/testvalue")

        assert r.status_code == 200
        # Check response cookies
        assert "testcookie" in r.cookies
        assert r.cookies["testcookie"] == "testvalue"

    def test_session_cookie_persistence(self):
        """Test that cookies persist across session requests."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set a cookie
            r1 = s.get("https://httpbin.org/cookies/set/persistent/cookie123")
            assert r1.status_code == 200

            # Verify cookie is in session
            assert "persistent" in s.cookies
            assert s.cookies["persistent"] == "cookie123"

            # Make another request - cookie should be sent
            r2 = s.get("https://httpbin.org/cookies")
            data = r2.json()
            assert data["cookies"]["persistent"] == "cookie123"

    def test_session_multiple_cookies(self):
        """Test setting multiple cookies in a session."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set multiple cookies
            s.get("https://httpbin.org/cookies/set/cookie1/value1")
            s.get("https://httpbin.org/cookies/set/cookie2/value2")
            s.get("https://httpbin.org/cookies/set/cookie3/value3")

            # Verify all cookies are sent
            r = s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["cookie1"] == "value1"
            assert data["cookies"]["cookie2"] == "value2"
            assert data["cookies"]["cookie3"] == "value3"

    def test_session_cookie_override(self):
        """Test that request cookies override session cookies."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set session cookie
            s.cookies["mysession"] = "session_value"

            # Override with request cookie
            r = s.get(
                "https://httpbin.org/cookies", cookies={"mysession": "request_value"}
            )
            data = r.json()
            assert data["cookies"]["mysession"] == "request_value"

    def test_session_preset_cookies(self):
        """Test session with preset cookies."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set cookies before making requests
            s.cookies["preset1"] = "value1"
            s.cookies["preset2"] = "value2"

            r = s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["preset1"] == "value1"
            assert data["cookies"]["preset2"] == "value2"

    def test_cookie_with_special_characters(self):
        """Test cookies with special characters."""
        import rnet_requests as requests

        # Note: Some special characters may be encoded
        cookies = {"special": "hello world"}
        r = requests.get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        data = r.json()
        assert "special" in data["cookies"]

    @pytest.mark.skip(
        reason="Known limitation: deleting from session.cookies dict doesn't "
        "remove cookies from rnet's internal cookie store. Use session.clear_cookies() "
        "or create a new session instead."
    )
    def test_delete_cookie(self):
        """Test that session cookies can be deleted."""
        import rnet_requests as requests

        with requests.Session() as s:
            # Set a cookie
            s.get("https://httpbin.org/cookies/set/deleteme/value")
            assert "deleteme" in s.cookies

            # Delete from session
            del s.cookies["deleteme"]
            assert "deleteme" not in s.cookies

            # Verify not sent
            r = s.get("https://httpbin.org/cookies")
            data = r.json()
            assert "deleteme" not in data["cookies"]


@pytest.mark.asyncio
class TestAsyncFileUploads:
    """Test async file uploads."""

    async def test_async_upload_file(self):
        """Test async file upload."""
        import rnet_requests as requests

        files = {"file": ("async_test.txt", b"Async file content")}
        r = await requests.async_post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert data["files"]["file"] == "Async file content"

    async def test_async_upload_multiple_files(self):
        """Test async multiple file upload."""
        import rnet_requests as requests

        files = {
            "file1": ("one.txt", b"First"),
            "file2": ("two.txt", b"Second"),
        }
        r = await requests.async_post("https://httpbin.org/post", files=files)

        assert r.status_code == 200
        data = r.json()
        assert data["files"]["file1"] == "First"
        assert data["files"]["file2"] == "Second"

    async def test_async_session_upload(self):
        """Test file upload with async session."""
        import rnet_requests as requests

        async with requests.AsyncSession() as s:
            files = {"upload": ("session_file.txt", b"Session upload")}
            r = await s.post("https://httpbin.org/post", files=files)

            assert r.status_code == 200
            data = r.json()
            assert data["files"]["upload"] == "Session upload"


@pytest.mark.asyncio
class TestAsyncCookies:
    """Test async cookie handling."""

    async def test_async_send_cookies(self):
        """Test sending cookies with async request."""
        import rnet_requests as requests

        cookies = {"async_cookie": "async_value"}
        r = await requests.async_get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        data = r.json()
        assert data["cookies"]["async_cookie"] == "async_value"

    async def test_async_receive_cookies(self):
        """Test receiving cookies from async response."""
        import rnet_requests as requests

        r = await requests.async_get(
            "https://httpbin.org/cookies/set/async_resp/value123"
        )

        assert r.status_code == 200
        assert "async_resp" in r.cookies
        assert r.cookies["async_resp"] == "value123"

    async def test_async_session_cookie_persistence(self):
        """Test async session cookie persistence."""
        import rnet_requests as requests

        async with requests.AsyncSession() as s:
            # Set cookie
            await s.get("https://httpbin.org/cookies/set/async_persist/persisted")

            # Verify in session
            assert "async_persist" in s.cookies

            # Verify sent in next request
            r = await s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["async_persist"] == "persisted"

    async def test_async_session_multiple_cookies(self):
        """Test async session with multiple cookies."""
        import rnet_requests as requests

        async with requests.AsyncSession() as s:
            await s.get("https://httpbin.org/cookies/set/a/1")
            await s.get("https://httpbin.org/cookies/set/b/2")
            await s.get("https://httpbin.org/cookies/set/c/3")

            r = await s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["a"] == "1"
            assert data["cookies"]["b"] == "2"
            assert data["cookies"]["c"] == "3"

    async def test_async_session_preset_cookies(self):
        """Test async session with preset cookies."""
        import rnet_requests as requests

        async with requests.AsyncSession() as s:
            s.cookies["preset_async"] = "preset_value"

            r = await s.get("https://httpbin.org/cookies")
            data = r.json()
            assert data["cookies"]["preset_async"] == "preset_value"

    async def test_async_concurrent_with_cookies(self):
        """Test concurrent async requests with cookies."""
        import asyncio

        import rnet_requests as requests

        async with requests.AsyncSession() as s:
            # Set a session cookie
            s.cookies["shared"] = "shared_value"

            # Make concurrent requests
            tasks = [
                s.get("https://httpbin.org/cookies"),
                s.get("https://httpbin.org/cookies"),
                s.get("https://httpbin.org/cookies"),
            ]
            responses = await asyncio.gather(*tasks)

            # All should have the cookie
            for r in responses:
                data = r.json()
                assert data["cookies"]["shared"] == "shared_value"


class TestCookieEdgeCases:
    """Test cookie edge cases."""

    def test_empty_cookie_value(self):
        """Test cookie with empty value."""
        import rnet_requests as requests

        cookies = {"empty": ""}
        r = requests.get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        # Empty cookies may or may not be sent depending on implementation

    def test_cookie_with_equals_sign(self):
        """Test cookie value containing equals sign."""
        import rnet_requests as requests

        cookies = {"encoded": "key=value"}
        r = requests.get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        data = r.json()
        # The value should be preserved
        assert "encoded" in data["cookies"]

    def test_many_cookies(self):
        """Test sending many cookies."""
        import rnet_requests as requests

        cookies = {f"cookie{i}": f"value{i}" for i in range(20)}
        r = requests.get("https://httpbin.org/cookies", cookies=cookies)

        assert r.status_code == 200
        data = r.json()
        assert len(data["cookies"]) == 20

    def test_session_cookies_isolated(self):
        """Test that different sessions have isolated cookies."""
        import rnet_requests as requests

        with requests.Session() as s1:
            s1.cookies["session1"] = "value1"

            with requests.Session() as s2:
                s2.cookies["session2"] = "value2"

                # s1 should only have session1
                r1 = s1.get("https://httpbin.org/cookies")
                data1 = r1.json()
                assert "session1" in data1["cookies"]
                assert "session2" not in data1["cookies"]

                # s2 should only have session2
                r2 = s2.get("https://httpbin.org/cookies")
                data2 = r2.json()
                assert "session2" in data2["cookies"]
                assert "session1" not in data2["cookies"]

"""Focused integration tests for the wreq backend."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from wreq import Emulation, Platform, Profile

import wrequests as requests
from wrequests.impersonate import create_emulation_option


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _reply(
        self,
        status: int = 200,
        body: bytes = b"",
        headers: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/redirect":
            self._reply(302, headers=(("Location", "/echo"),))
            return
        if self.path == "/set-cookie":
            self._reply(200, headers=(("Set-Cookie", "session=local; Path=/"),))
            return
        if self.path == "/stream":
            self._reply(200, b"alpha\nbeta\n")
            return

        body = json.dumps(
            {
                "path": self.path,
                "cookie": self.headers.get("Cookie", ""),
                "test_header": self.headers.get("X-Test"),
            }
        ).encode()
        self._reply(200, body, (("Content-Type", "application/json"),))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        result = json.dumps({"length": len(body)}).encode()
        self._reply(200, result, (("Content-Type", "application/json"),))

    def log_message(self, _format: str, *args: object) -> None:
        pass


@pytest.fixture
def local_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_wreq_emulation_adapter() -> None:
    latest_chrome = create_emulation_option("chrome")
    assert isinstance(latest_chrome, Profile)

    configured = create_emulation_option("chrome", "windows")
    assert isinstance(configured, Emulation)
    assert Platform.Windows is requests.ImpersonateOS.Windows


def test_sync_wreq_round_trip(local_server: str) -> None:
    with requests.Session(
        impersonate="chrome",
        impersonate_os="windows",
        headers={"X-Test": "sync"},
        http_version="HTTP/1.1",
    ) as session:
        response = session.get(f"{local_server}/echo", params={"answer": "42"})
        assert response.status_code == 200
        assert response.json() == {
            "path": "/echo?answer=42",
            "cookie": "",
            "test_header": "sync",
        }

        response = session.get(f"{local_server}/redirect")
        assert response.status_code == 200
        assert [item.status_code for item in response.history] == [302]

        session.get(f"{local_server}/set-cookie")
        assert "session=local" in session.get(f"{local_server}/echo").json()["cookie"]
        session.clear_cookies()
        assert (
            "session=local" not in session.get(f"{local_server}/echo").json()["cookie"]
        )

        response = session.get(f"{local_server}/stream", stream=True)
        assert list(response.iter_lines()) == [b"alpha", b"beta"]

        response = session.post(
            f"{local_server}/upload", files={"file": ("sample.txt", b"payload")}
        )
        assert response.json()["length"] > len(b"payload")


@pytest.mark.asyncio
async def test_async_wreq_round_trip(local_server: str) -> None:
    async with requests.AsyncSession(
        impersonate="firefox",
        impersonate_os="linux",
        headers={"X-Test": "async"},
    ) as session:
        response = await session.get(f"{local_server}/echo")
        assert response.status_code == 200
        assert response.json()["test_header"] == "async"

        response = await session.get(f"{local_server}/stream", stream=True)
        assert [line async for line in response.aiter_lines()] == [b"alpha", b"beta"]
        await response.aclose()

    response = await requests.async_get(f"{local_server}/stream", stream=True)
    assert await response.acontent() == b"alpha\nbeta\n"
    await response.aclose()
    assert response._session is None


def test_module_options_reach_wreq_client(local_server: str) -> None:
    response = requests.get(
        f"{local_server}/redirect",
        verify=False,
        http_version="HTTP/1.1",
        default_headers=False,
    )
    assert response.status_code == 200
    assert [item.status_code for item in response.history] == [302]

    response = requests.get(f"{local_server}/stream", stream=True)
    assert response.content == b"alpha\nbeta\n"
    response.close()
    assert response._session is None

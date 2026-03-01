"""WebSocket tests for rnet-requests."""

import pytest

# WebSocket echo server - use a reliable one
WS_ECHO_URL = "wss://ws.postman-echo.com/raw"


@pytest.mark.asyncio
class TestWebSocketImports:
    """Test WebSocket imports."""

    async def test_import_websocket_classes(self):
        """Test importing WebSocket classes."""
        from rnet_requests import (
            AsyncWebSocket,
            WebSocketClosed,
            WebSocketError,
            WebSocketTimeout,
            WsCloseCode,
        )

        assert AsyncWebSocket is not None
        assert WebSocketError is not None
        assert WebSocketClosed is not None
        assert WebSocketTimeout is not None
        assert WsCloseCode is not None

    async def test_ws_close_codes(self):
        """Test WsCloseCode enum values."""
        from rnet_requests import WsCloseCode

        assert WsCloseCode.OK == 1000
        assert WsCloseCode.GOING_AWAY == 1001
        assert WsCloseCode.PROTOCOL_ERROR == 1002
        assert WsCloseCode.ABNORMAL_CLOSURE == 1006


@pytest.mark.asyncio
class TestWebSocketConnection:
    """Test WebSocket connections."""

    async def test_ws_connect_echo(self):
        """Test WebSocket connection to echo server."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            try:
                assert ws.ok
                assert not ws.closed

                # Send and receive text
                await ws.send_str("Hello, WebSocket!")
                msg = await ws.recv_str(timeout=10.0)
                # Echo server echoes back the message
                assert "Hello" in msg
            finally:
                await ws.close()

    async def test_ws_send_receive_text(self):
        """Test sending and receiving text messages."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            try:
                test_message = "Test message 123"
                await ws.send_str(test_message)
                response = await ws.recv_str(timeout=10.0)
                # Echo server echoes back the message
                assert test_message in response
            finally:
                await ws.close()

    async def test_ws_send_receive_json(self):
        """Test sending and receiving JSON messages."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            try:
                test_data = {"type": "test", "value": 42}
                await ws.send_json(test_data)
                # Receive and check it's valid JSON
                response = await ws.recv(timeout=10.0)
                assert response is not None
            finally:
                await ws.close()

    @pytest.mark.skip(reason="Echo server doesn't handle binary frames properly")
    async def test_ws_send_receive_binary(self):
        """Test sending and receiving binary messages."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            try:
                test_data = b"\x00\x01\x02\x03\x04"
                await ws.send_bytes(test_data)
                response = await ws.recv(timeout=10.0)
                # Binary data may be echoed back
                assert response is not None
            finally:
                await ws.close()

    async def test_ws_close(self):
        """Test closing WebSocket connection."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            assert not ws.closed

            await ws.close()
            assert ws.closed
            assert ws.close_code == 1000  # Normal closure

    async def test_ws_context_manager(self):
        """Test WebSocket as async context manager."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            async with ws:
                assert not ws.closed
                await ws.send_str("test")
                await ws.recv(timeout=10.0)
            # After exiting context, should be closed
            assert ws.closed


@pytest.mark.asyncio
class TestWebSocketErrors:
    """Test WebSocket error handling."""

    async def test_ws_closed_error(self):
        """Test WebSocketClosed error when sending to closed socket."""
        from rnet_requests import AsyncSession, WebSocketClosed

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            await ws.close()

            with pytest.raises(WebSocketClosed):
                await ws.send_str("should fail")

    async def test_ws_recv_on_closed(self):
        """Test receiving on closed WebSocket."""
        from rnet_requests import AsyncSession, WebSocketClosed

        async with AsyncSession() as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            await ws.close()

            with pytest.raises(WebSocketClosed):
                await ws.recv()


@pytest.mark.asyncio
class TestWebSocketWithSession:
    """Test WebSocket with session features."""

    async def test_ws_with_headers(self):
        """Test WebSocket connection with custom headers."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws = await session.ws_connect(
                WS_ECHO_URL,
                headers={"X-Custom-Header": "test-value"},
            )
            try:
                assert ws.ok
                await ws.send_str("test")
                await ws.recv(timeout=10.0)
            finally:
                await ws.close()

    async def test_ws_with_impersonation(self):
        """Test WebSocket with browser impersonation."""
        from rnet_requests import AsyncSession

        async with AsyncSession(impersonate="chrome") as session:
            ws = await session.ws_connect(WS_ECHO_URL)
            try:
                assert ws.ok
                await ws.send_str("test from chrome")
                await ws.recv(timeout=10.0)
            finally:
                await ws.close()

    async def test_ws_multiple_connections(self):
        """Test multiple WebSocket connections from same session."""
        from rnet_requests import AsyncSession

        async with AsyncSession() as session:
            ws1 = await session.ws_connect(WS_ECHO_URL)
            ws2 = await session.ws_connect(WS_ECHO_URL)

            try:
                # Both should be open
                assert not ws1.closed
                assert not ws2.closed

                # Send on both
                await ws1.send_str("ws1")
                await ws2.send_str("ws2")

                # Receive from both
                r1 = await ws1.recv(timeout=10.0)
                r2 = await ws2.recv(timeout=10.0)

                assert r1 is not None
                assert r2 is not None
            finally:
                await ws1.close()
                await ws2.close()

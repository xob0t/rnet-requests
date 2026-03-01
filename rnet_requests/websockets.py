"""
rnet_requests.websockets
~~~~~~~~~~~~~~~~~~~~~~~~

WebSocket support using rnet's WebSocket client.
Provides a curl_cffi-compatible API.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import IntEnum
from functools import partial
from json import dumps, loads
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from rnet import Message as RnetMessage
from rnet import WebSocket as RnetWebSocket

from .exceptions import RequestException

if TYPE_CHECKING:
    from .async_session import AsyncSession

# Partial for dumps to ensure compact output
dumps = partial(dumps, separators=(",", ":"))

T = TypeVar("T")


class WsCloseCode(IntEnum):
    """WebSocket close codes per RFC 6455."""

    OK = 1000
    GOING_AWAY = 1001
    PROTOCOL_ERROR = 1002
    UNSUPPORTED_DATA = 1003
    UNKNOWN = 1005
    ABNORMAL_CLOSURE = 1006
    INVALID_DATA = 1007
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009
    MANDATORY_EXTENSION = 1010
    INTERNAL_ERROR = 1011
    SERVICE_RESTART = 1012
    TRY_AGAIN_LATER = 1013
    BAD_GATEWAY = 1014
    TLS_HANDSHAKE = 1015
    UNAUTHORIZED = 3000
    FORBIDDEN = 3003
    TIMEOUT = 3008


class WebSocketError(RequestException):
    """WebSocket-specific error."""

    def __init__(self, message: str, code: WsCloseCode | int = 0):
        super().__init__(message, code)
        self.code = code


class WebSocketClosed(WebSocketError):
    """WebSocket is already closed."""

    pass


class WebSocketTimeout(WebSocketError):
    """WebSocket operation timed out."""

    pass


class AsyncWebSocket:
    """
    An async WebSocket implementation using rnet.

    This class wraps rnet's WebSocket to provide a curl_cffi-compatible API.

    Example usage:
        >>> async with session.ws_connect("wss://echo.websocket.org") as ws:
        ...     await ws.send_str("Hello!")
        ...     msg = await ws.recv_str()
        ...     print(msg)
    """

    __slots__ = (
        "_ws",
        "_session",
        "_closed",
        "_close_code",
        "_close_reason",
        "autoclose",
    )

    def __init__(
        self,
        ws: RnetWebSocket,
        session: AsyncSession | None = None,
        *,
        autoclose: bool = True,
    ):
        """Initialize AsyncWebSocket.

        Args:
            ws: The underlying rnet WebSocket.
            session: The session that created this WebSocket.
            autoclose: Whether to auto-close on receiving close frame.
        """
        self._ws = ws
        self._session = session
        self._closed = False
        self._close_code: int | None = None
        self._close_reason: str | None = None
        self.autoclose = autoclose

    @property
    def closed(self) -> bool:
        """Whether the WebSocket is closed."""
        return self._closed

    @property
    def close_code(self) -> int | None:
        """The WebSocket close code, if closed."""
        return self._close_code

    @property
    def close_reason(self) -> str | None:
        """The WebSocket close reason, if closed."""
        return self._close_reason

    @property
    def ok(self) -> bool:
        """Whether the WebSocket connection was successful."""
        # rnet v3: .ok attribute removed, check status code instead
        # 101 Switching Protocols indicates successful WebSocket upgrade
        return self.status == 101

    @property
    def status(self) -> int:
        """The HTTP status code of the WebSocket handshake."""
        # rnet v3: status is a StatusCode object, use .as_int()
        return self._ws.status.as_int()

    @property
    def headers(self) -> Any:
        """The response headers from the WebSocket handshake."""
        return self._ws.headers

    @property
    def protocol(self) -> str | None:
        """The negotiated WebSocket subprotocol."""
        return self._ws.protocol

    async def __aenter__(self) -> AsyncWebSocket:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def __aiter__(self) -> AsyncWebSocket:
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")
        return self

    async def __anext__(self) -> bytes:
        msg = await self.recv()
        if msg is None:
            raise StopAsyncIteration
        return msg

    async def recv(self, *, timeout: float | None = None) -> bytes | None:
        """Receive a message from the WebSocket.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            The received message data, or None if connection closed.

        Raises:
            WebSocketClosed: If the WebSocket is closed.
            WebSocketTimeout: If the operation times out.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        try:
            if timeout is not None:
                msg = await asyncio.wait_for(self._ws.recv(), timeout)
            else:
                msg = await self._ws.recv()

            if msg is None:
                return None

            # Check for close message
            if msg.close is not None:
                self._close_code, self._close_reason = msg.close
                if self.autoclose:
                    await self.close()
                return None

            # Return data (text or binary)
            return msg.data

        except TimeoutError as e:
            raise WebSocketTimeout("WebSocket recv timed out") from e
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def recv_str(self, *, timeout: float | None = None) -> str:
        """Receive a text message.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            The received text message.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        try:
            if timeout is not None:
                msg = await asyncio.wait_for(self._ws.recv(), timeout)
            else:
                msg = await self._ws.recv()

            if msg is None or msg.text is None:
                raise WebSocketError("Not a text message", WsCloseCode.INVALID_DATA)

            return msg.text

        except TimeoutError as e:
            raise WebSocketTimeout("WebSocket recv timed out") from e

    async def recv_json(
        self,
        *,
        loads: Callable[[str], T] = loads,
        timeout: float | None = None,
    ) -> T:
        """Receive a JSON message.

        Args:
            loads: JSON decoder function.
            timeout: Optional timeout in seconds.

        Returns:
            The decoded JSON data.
        """
        text = await self.recv_str(timeout=timeout)
        return loads(text)

    async def send(self, data: str | bytes) -> None:
        """Send a message.

        Args:
            data: The data to send (text or binary).
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        if isinstance(data, str):
            msg = RnetMessage.from_text(data)
        else:
            msg = RnetMessage.from_binary(data)

        try:
            await self._ws.send(msg)
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def send_str(self, data: str) -> None:
        """Send a text message.

        Args:
            data: The text to send.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        try:
            await self._ws.send(RnetMessage.from_text(data))
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary message.

        Args:
            data: The binary data to send.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        try:
            await self._ws.send(RnetMessage.from_binary(data))
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def send_json(
        self,
        data: Any,
        *,
        dumps: Callable[[Any], str] = dumps,
    ) -> None:
        """Send a JSON message.

        Args:
            data: The data to JSON-encode and send.
            dumps: JSON encoder function.
        """
        await self.send_str(dumps(data))

    async def ping(self, data: str | bytes = b"") -> None:
        """Send a ping frame.

        Args:
            data: Optional ping data.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        if isinstance(data, str):
            data = data.encode()

        try:
            await self._ws.send(RnetMessage.from_ping(data))
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def pong(self, data: str | bytes = b"") -> None:
        """Send a pong frame.

        Args:
            data: Optional pong data.
        """
        if self._closed:
            raise WebSocketClosed("WebSocket is closed")

        if isinstance(data, str):
            data = data.encode()

        try:
            # Use from_pong if available, otherwise create binary message
            if hasattr(RnetMessage, "from_pong"):
                await self._ws.send(RnetMessage.from_pong(data))
            else:
                # Fallback: pong is similar to ping in WebSocket protocol
                await self._ws.send(RnetMessage.from_ping(data))
        except Exception as e:
            raise WebSocketError(str(e)) from e

    async def close(
        self,
        code: int = WsCloseCode.OK,
        reason: str = "",
    ) -> None:
        """Close the WebSocket connection.

        Args:
            code: The close code (default: 1000 OK).
            reason: Optional close reason.
        """
        if self._closed:
            return

        self._closed = True
        self._close_code = code
        self._close_reason = reason

        import contextlib

        with contextlib.suppress(Exception):
            await self._ws.close(code, reason if reason else None)

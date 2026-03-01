"""
rnet_requests.multipart
~~~~~~~~~~~~~~~~~~~~~~~

Multipart form data support compatible with curl_cffi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rnet import Multipart as RnetMultipart
from rnet import Part as RnetPart


class Multipart:
    """
    Multipart form data builder compatible with curl_cffi's CurlMime.

    This class provides an easy way to build multipart form data for file uploads.

    Example usage:
        >>> mp = Multipart()
        >>> mp.addpart("file", filename="test.txt", data=b"Hello, World!")
        >>> mp.addpart("field", data=b"value")
        >>> response = session.post(url, multipart=mp)

    Or using the from_dict class method:
        >>> mp = Multipart.from_dict({
        ...     "file": ("filename.txt", b"content", "text/plain"),
        ...     "field": "value"
        ... })
    """

    def __init__(self):
        """Initialize an empty Multipart form."""
        self._parts: list[tuple[str, Any]] = []

    def addpart(
        self,
        name: str,
        *,
        content_type: str | None = None,
        filename: str | None = None,
        local_path: str | bytes | Path | None = None,
        data: bytes | None = None,
    ) -> None:
        """Add a part to the multipart form.

        Note: You can only use either local_path or data, not both.

        Args:
            name: Name of the field.
            content_type: Content-Type for the field (e.g., "image/png").
            filename: Filename for the server.
            local_path: Path to file on local disk to upload.
            data: File content as bytes to upload.
        """
        if local_path is not None and data is not None:
            raise ValueError("Cannot specify both local_path and data")

        if local_path is not None:
            # Read file from disk
            path = Path(local_path)
            data = path.read_bytes()
            if filename is None:
                filename = path.name

        self._parts.append(
            {
                "name": name,
                "data": data,
                "filename": filename,
                "content_type": content_type,
            }
        )

    def _to_rnet_multipart(self) -> RnetMultipart:
        """Convert to rnet Multipart object."""
        parts = []
        for part_info in self._parts:
            name = part_info["name"]
            data = part_info["data"]
            filename = part_info["filename"]
            content_type = part_info["content_type"]

            if data is None:
                data = b""

            # Convert string data to bytes
            if isinstance(data, str):
                data = data.encode("utf-8")

            part = RnetPart(name, data, filename=filename, mime=content_type)
            parts.append(part)

        return RnetMultipart(*parts)

    @classmethod
    def from_dict(
        cls,
        fields: dict,
    ) -> Multipart:
        """Create a Multipart from a dictionary.

        The dictionary can contain:
        - Simple values: {"field": "value"} or {"field": b"bytes"}
        - Tuples with filename: {"file": ("filename.txt", b"content")}
        - Tuples with content type: {"file": ("filename.txt", b"content", "text/plain")}

        Args:
            fields: Dictionary of field names to values.

        Returns:
            A new Multipart instance.
        """
        mp = cls()
        for name, value in fields.items():
            if isinstance(value, tuple):
                if len(value) == 2:
                    filename, data = value
                    content_type = None
                elif len(value) >= 3:
                    filename, data, content_type = value[0], value[1], value[2]
                else:
                    raise ValueError(f"Invalid tuple format for field {name}")

                # Handle file-like objects
                if hasattr(data, "read"):
                    data = data.read()

                mp.addpart(
                    name, filename=filename, data=data, content_type=content_type
                )
            else:
                # Simple value
                data = value
                if isinstance(data, str):
                    data = data.encode("utf-8")
                elif hasattr(data, "read"):
                    data = data.read()
                mp.addpart(name, data=data)

        return mp

    @classmethod
    def from_list(
        cls,
        parts: list[dict[str, Any]],
    ) -> Multipart:
        """Create a Multipart from a list of part dictionaries.

        This method provides curl_cffi CurlMime.from_list() compatibility.

        Each dict can contain:
        - name: Field name (required)
        - data: Content as bytes or str
        - filename: Filename for the server
        - content_type: MIME type (e.g., "image/png")
        - local_path: Path to file on disk (alternative to data)

        Args:
            parts: List of dictionaries describing each part.

        Returns:
            A new Multipart instance.

        Example:
            >>> mp = Multipart.from_list([
            ...     {"name": "file", "filename": "test.txt", "data": b"content"},
            ...     {"name": "field", "data": "value"},
            ...     {"name": "upload", "local_path": "/path/to/file.pdf"},
            ... ])
        """
        mp = cls()
        for part in parts:
            name = part.get("name")
            if not name:
                raise ValueError("Each part must have a 'name' field")

            data = part.get("data")
            filename = part.get("filename")
            content_type = part.get("content_type")
            local_path = part.get("local_path")

            # Handle string data
            if isinstance(data, str):
                data = data.encode("utf-8")

            # Handle file-like objects
            if data is not None and hasattr(data, "read"):
                data = data.read()

            mp.addpart(
                name,
                data=data,
                filename=filename,
                content_type=content_type,
                local_path=local_path,
            )

        return mp

    def __len__(self) -> int:
        """Return the number of parts."""
        return len(self._parts)

    def __repr__(self) -> str:
        return f"<Multipart parts={len(self._parts)}>"

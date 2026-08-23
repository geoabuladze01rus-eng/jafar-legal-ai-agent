from __future__ import annotations

from typing import Protocol


class AttachmentStorage(Protocol):
    """Durable boundary for storing original legal-email attachments."""

    def put(self, *, path: str, content: bytes, media_type: str | None = None) -> str: ...


class InMemoryAttachmentStorage:
    """Deterministic storage implementation for tests and local development."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, str | None]] = {}

    def put(self, *, path: str, content: bytes, media_type: str | None = None) -> str:
        self.files[path] = (content, media_type)
        return path

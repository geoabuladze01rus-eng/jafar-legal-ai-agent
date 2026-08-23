from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AttachmentMaterializer(Protocol):
    """Resolves an external attachment reference into raw bytes."""

    def materialize(self, file_uri: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class MaterializedAttachment:
    filename: str
    content: bytes
    media_type: str | None = None


class InMemoryAttachmentMaterializer:
    """Small deterministic implementation for tests and local adapters."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def materialize(self, file_uri: str) -> bytes:
        try:
            return self.files[file_uri]
        except KeyError as exc:
            raise FileNotFoundError(f"Attachment reference not found: {file_uri}") from exc

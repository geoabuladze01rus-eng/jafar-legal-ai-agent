from __future__ import annotations

from typing import Protocol

from .attachment_storage import AttachmentStorage


class SupabaseUploadClient(Protocol):
    """Minimal boundary for the authenticated attachment-upload function."""

    def invoke(self, function_name: str, body: dict) -> dict: ...


class SupabaseAttachmentStorage(AttachmentStorage):
    """Stores originals through the JWT-protected Jafar upload function."""

    def __init__(self, client: SupabaseUploadClient) -> None:
        self.client = client

    def put(self, *, path: str, content: bytes, media_type: str | None = None) -> str:
        import base64
        payload = {
            "message_id": path.split("/", 1)[0],
            "filename": path.rsplit("/", 1)[-1],
            "media_type": media_type,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        result = self.client.invoke("jafar-attachment-upload", payload)
        return str(result["path"])

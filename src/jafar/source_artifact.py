from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceArtifactIdentity:
    """Provider provenance used for idempotency, never authorization."""

    provider: str
    message_id: str
    attachment_id: str

    def __post_init__(self) -> None:
        if not all((self.provider.strip(), self.message_id.strip(), self.attachment_id.strip())):
            raise ValueError("source artifact identity requires provider, message_id and attachment_id")

    @property
    def processing_key(self) -> str:
        canonical = json.dumps(
            {"attachment_id": self.attachment_id, "message_id": self.message_id, "provider": self.provider},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def source_artifact_identity(provider: str, message_id: str, attachment_id: str | None) -> SourceArtifactIdentity | None:
    if not attachment_id or not attachment_id.strip():
        return None
    return SourceArtifactIdentity(provider=provider, message_id=message_id, attachment_id=attachment_id)

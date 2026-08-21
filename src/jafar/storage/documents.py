from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class StoredDocument:
    document_id: str
    filename: str
    content_type: str
    source: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    matter_id: str | None = None


class DocumentStore:
    """Small repository boundary; persistent DB/object storage can replace it later."""

    def __init__(self) -> None:
        self._documents: dict[str, StoredDocument] = {}

    def save(self, document: StoredDocument) -> StoredDocument:
        self._documents[document.document_id] = document
        return document

    def get(self, document_id: str) -> StoredDocument | None:
        return self._documents.get(document_id)

    def list_for_matter(self, matter_id: str) -> list[StoredDocument]:
        return [doc for doc in self._documents.values() if doc.matter_id == matter_id]

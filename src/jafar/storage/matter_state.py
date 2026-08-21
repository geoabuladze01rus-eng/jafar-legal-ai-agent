from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MatterState:
    matter_id: str
    title: str
    client_id: str | None = None
    status: str = "active"
    document_ids: list[str] = field(default_factory=list)
    message_ids: list[str] = field(default_factory=list)
    deadline_ids: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def attach_document(self, document_id: str) -> None:
        if document_id not in self.document_ids:
            self.document_ids.append(document_id)
        self.touch()

    def attach_message(self, message_id: str) -> None:
        if message_id not in self.message_ids:
            self.message_ids.append(message_id)
        self.touch()

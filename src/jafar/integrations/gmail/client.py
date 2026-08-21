from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GmailMessage:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    received_at: str
    snippet: str
    has_attachments: bool


class GmailTransport(Protocol):
    async def list_messages(self, query: str = "in:inbox", page_token: str | None = None) -> tuple[list[GmailMessage], str | None]: ...
    async def fetch_message(self, message_id: str) -> GmailMessage: ...


class GmailIngestionService:
    def __init__(self, transport: GmailTransport):
        self.transport = transport

    async def ingest_page(self, query: str = "in:inbox", page_token: str | None = None):
        messages, next_token = await self.transport.list_messages(query, page_token)
        return messages, next_token

    async def ingest_message(self, message_id: str):
        return await self.transport.fetch_message(message_id)

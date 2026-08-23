from __future__ import annotations

from typing import Protocol


class ProcessingLedger(Protocol):
    """Durable boundary used to prevent duplicate message processing."""

    def has_processed(self, message_id: str) -> bool: ...

    def mark_processed(self, message_id: str) -> None: ...


class InMemoryProcessingLedger:
    """Deterministic implementation for local runs and tests."""

    def __init__(self) -> None:
        self._processed: set[str] = set()

    def has_processed(self, message_id: str) -> bool:
        return message_id in self._processed

    def mark_processed(self, message_id: str) -> None:
        self._processed.add(message_id)

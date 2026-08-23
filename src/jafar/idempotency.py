from __future__ import annotations

from typing import Protocol


class ProcessingLedger(Protocol):
    """Atomic boundary used to claim a message before processing it."""

    def claim(self, message_id: str, *, sender: str, subject: str, received_at: str) -> bool: ...

    def mark_processed(self, message_id: str) -> None: ...

    def mark_failed(self, message_id: str) -> None: ...


class InMemoryProcessingLedger:
    """Deterministic implementation for local runs and tests."""

    def __init__(self) -> None:
        self._processed: set[str] = set()
        self._claimed: set[str] = set()

    def claim(self, message_id: str, *, sender: str, subject: str, received_at: str) -> bool:
        if message_id in self._claimed or message_id in self._processed:
            return False
        self._claimed.add(message_id)
        return True

    def mark_processed(self, message_id: str) -> None:
        self._claimed.discard(message_id)
        self._processed.add(message_id)

    def mark_failed(self, message_id: str) -> None:
        self._claimed.discard(message_id)

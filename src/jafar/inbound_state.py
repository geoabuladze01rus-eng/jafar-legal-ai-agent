from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class InboundStateStore(Protocol):
    async def claim_update(self, update_id: int) -> bool: ...


@dataclass
class InMemoryInboundStateStore:
    seen: set[int]

    def __init__(self) -> None:
        self.seen = set()

    async def claim_update(self, update_id: int) -> bool:
        if update_id in self.seen:
            return False
        self.seen.add(update_id)
        return True

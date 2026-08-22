from __future__ import annotations

from collections import deque


class UpdateDeduplicator:
    def __init__(self, max_size: int = 10_000) -> None:
        if max_size < 1:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self._seen: set[int] = set()
        self._order: deque[int] = deque()

    def accept(self, update_id: int) -> bool:
        if update_id in self._seen:
            return False
        self._seen.add(update_id)
        self._order.append(update_id)
        if len(self._order) > self.max_size:
            expired = self._order.popleft()
            self._seen.discard(expired)
        return True

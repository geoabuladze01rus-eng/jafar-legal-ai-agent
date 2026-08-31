from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from .memory_models import MemoryKind, MemoryRecord, MemorySearchResult


class SupabaseMemoryRepository:
    def __init__(self, client: Any, owner_user_id: str) -> None:
        self.client = client
        self.owner_user_id = owner_user_id

    def add(
        self,
        *,
        kind: MemoryKind,
        content: str,
        embedding: tuple[float, ...],
        matter_id: str | None = None,
        source: str | None = None,
        confidence: float = 1.0,
    ) -> MemoryRecord:
        text = content.strip()
        if not text:
            raise ValueError("memory content is required")
        if len(embedding) != 1536:
            raise ValueError("memory embedding must have 1536 dimensions")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("memory confidence must be between 0 and 1")

        memory_id = str(uuid4())
        payload = {
            "id": memory_id,
            "owner_user_id": self.owner_user_id,
            "matter_id": matter_id,
            "kind": kind.value,
            "content": text,
            "source": source,
            "confidence": confidence,
            "embedding": list(embedding),
        }
        response = self.client.table("assistant_memories").insert(payload).execute()
        row = response.data[0] if isinstance(response.data, list) and response.data else response.data
        if not row:
            row = payload | {"created_at": datetime.utcnow().isoformat()}
        return self._memory(row)

    def list(self, *, matter_id: str | None = None, limit: int = 100) -> list[MemoryRecord]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        query = (
            self.client.table("assistant_memories")
            .select("id,owner_user_id,matter_id,kind,content,source,confidence,created_at")
            .eq("owner_user_id", self.owner_user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if matter_id is not None:
            query = query.eq("matter_id", matter_id)
        response = query.execute()
        return [self._memory(row) for row in (response.data or [])]

    def search(
        self,
        *,
        embedding: tuple[float, ...],
        matter_id: str | None = None,
        limit: int = 8,
        min_similarity: float = 0.0,
    ) -> list[MemorySearchResult]:
        if len(embedding) != 1536:
            raise ValueError("memory embedding must have 1536 dimensions")
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")
        response = self.client.rpc(
            "match_assistant_memories",
            {
                "p_owner_user_id": self.owner_user_id,
                "p_query_embedding": list(embedding),
                "p_matter_id": matter_id,
                "p_match_count": limit,
                "p_min_similarity": min_similarity,
            },
        ).execute()
        results: list[MemorySearchResult] = []
        for row in response.data or []:
            if row.get("owner_user_id") != self.owner_user_id:
                raise RuntimeError("memory search returned a different owner")
            if matter_id is not None and row.get("matter_id") not in (None, matter_id):
                raise RuntimeError("memory search returned a different matter")
            results.append(
                MemorySearchResult(
                    memory=self._memory(row),
                    similarity=float(row.get("similarity", 0.0)),
                )
            )
        return results

    def delete(self, memory_id: str) -> bool:
        response = (
            self.client.table("assistant_memories")
            .delete()
            .eq("id", memory_id)
            .eq("owner_user_id", self.owner_user_id)
            .execute()
        )
        return bool(response.data)

    @staticmethod
    def _memory(row: dict[str, Any]) -> MemoryRecord:
        created = row.get("created_at")
        created_at = datetime.fromisoformat(created.replace("Z", "+00:00")) if isinstance(created, str) else datetime.utcnow()
        return MemoryRecord(
            id=str(row["id"]),
            owner_user_id=str(row["owner_user_id"]),
            matter_id=row.get("matter_id"),
            kind=MemoryKind(row["kind"]),
            content=str(row["content"]),
            source=row.get("source"),
            confidence=float(row.get("confidence", 1.0)),
            created_at=created_at,
        )

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .memory_models import MemoryKind


router = APIRouter(prefix="/v1/memory", tags=["memory"])


class RememberRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    kind: MemoryKind = MemoryKind.NOTE
    matter_id: str | None = None
    source: str | None = Field(default=None, max_length=500)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    matter_id: str | None = None
    limit: int = Field(default=8, ge=1, le=50)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)


def _service(request: Request):
    service = getattr(request.app.state, "memory_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Long-term memory is not configured")
    return service


@router.post("/remember")
def remember(body: RememberRequest, request: Request):
    try:
        memory = _service(request).remember(
            content=body.content,
            kind=body.kind,
            matter_id=body.matter_id,
            source=body.source,
            confidence=body.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Memory write failed") from exc
    return {
        "id": memory.id,
        "kind": memory.kind.value,
        "content": memory.content,
        "matter_id": memory.matter_id,
        "source": memory.source,
        "confidence": memory.confidence,
        "created_at": memory.created_at.isoformat(),
    }


@router.post("/recall")
def recall(body: RecallRequest, request: Request):
    try:
        results = _service(request).recall(
            body.query,
            matter_id=body.matter_id,
            limit=body.limit,
            min_similarity=body.min_similarity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Memory recall failed") from exc
    return {
        "results": [
            {
                "id": result.memory.id,
                "kind": result.memory.kind.value,
                "content": result.memory.content,
                "matter_id": result.memory.matter_id,
                "source": result.memory.source,
                "confidence": result.memory.confidence,
                "created_at": result.memory.created_at.isoformat(),
                "similarity": result.similarity,
            }
            for result in results
        ]
    }


@router.get("")
def list_memories(request: Request, matter_id: str | None = None, limit: int = 100):
    try:
        memories = _service(request).list_memories(matter_id=matter_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "results": [
            {
                "id": memory.id,
                "kind": memory.kind.value,
                "content": memory.content,
                "matter_id": memory.matter_id,
                "source": memory.source,
                "confidence": memory.confidence,
                "created_at": memory.created_at.isoformat(),
            }
            for memory in memories
        ]
    }


@router.delete("/{memory_id}", status_code=204)
def forget(memory_id: str, request: Request):
    try:
        deleted = _service(request).forget(memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return None

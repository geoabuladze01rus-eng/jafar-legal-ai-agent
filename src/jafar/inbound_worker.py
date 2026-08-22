from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .comment_pipeline import CommentPipelineResult, process_update
from .inbound_state import InboundStateStore


class InboundAuditSink(Protocol):
    async def write(self, result: CommentPipelineResult) -> None: ...


@dataclass(frozen=True)
class InboundWorkerResult:
    processed: bool
    duplicate: bool
    result: CommentPipelineResult | None


class TelegramInboundWorker:
    def __init__(self, state: InboundStateStore, audit_sink: InboundAuditSink | None = None) -> None:
        self.state = state
        self.audit_sink = audit_sink

    async def handle_update(self, update: dict[str, Any]) -> InboundWorkerResult:
        update_id = int(update.get("update_id", 0))
        if not await self.state.claim_update(update_id):
            return InboundWorkerResult(processed=False, duplicate=True, result=None)
        result = process_update(update)
        if result is not None and self.audit_sink is not None:
            await self.audit_sink.write(result)
        return InboundWorkerResult(processed=result is not None, duplicate=False, result=result)

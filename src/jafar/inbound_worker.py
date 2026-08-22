from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .comment_pipeline import CommentPipelineResult, process_update
from .inbound_state import InboundStateStore
from .response_safety_gate import evaluate_response
from .supabase_inbound_state import SupabaseInboundStateStore


class InboundAuditSink(Protocol):
    async def write(self, result: CommentPipelineResult) -> None: ...


@dataclass(frozen=True)
class InboundWorkerResult:
    processed: bool
    duplicate: bool
    blocked_by_safety_gate: bool
    result: CommentPipelineResult | None


class TelegramInboundWorker:
    def __init__(self, state: InboundStateStore, audit_sink: InboundAuditSink | None = None) -> None:
        self.state = state
        self.audit_sink = audit_sink

    async def handle_update(self, update: dict[str, Any]) -> InboundWorkerResult:
        update_id = int(update.get("update_id", 0))
        if not await self.state.claim_update(update_id):
            return InboundWorkerResult(False, True, False, None)

        result = process_update(update)
        if result is None:
            return InboundWorkerResult(False, False, False, None)

        safety = evaluate_response(result.draft.intent, result.draft.decision)
        if not safety.allowed:
            if self.audit_sink is not None:
                await self.audit_sink.write(result)
            return InboundWorkerResult(False, False, True, result)

        if self.audit_sink is not None:
            await self.audit_sink.write(result)
        return InboundWorkerResult(True, False, False, result)


def build_supabase_inbound_worker(
    supabase_url: str,
    supabase_service_key: str,
    audit_sink: InboundAuditSink | None = None,
) -> TelegramInboundWorker:
    state = SupabaseInboundStateStore(supabase_url, supabase_service_key)
    return TelegramInboundWorker(state, audit_sink)

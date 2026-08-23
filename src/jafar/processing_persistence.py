from __future__ import annotations

import json
from typing import Protocol

from .email_pipeline import EmailPipelineResult
from .inbox import InboxMessage


class ProcessingResultStore(Protocol):
    """Durable boundary for saving the outcome of an email processing run."""

    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None: ...


class InMemoryProcessingResultStore:
    def __init__(self) -> None:
        self.results: dict[str, EmailPipelineResult] = {}

    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None:
        self.results[message.message_id] = result


class SupabaseProcessingResultStore:
    """Persists normalized email triage and document analyses through RPC.

    The concrete Supabase SDK is intentionally kept outside the domain layer.
    The RPC should perform the email upsert and analysis inserts atomically.
    """

    def __init__(self, client: object) -> None:
        self.client = client

    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None:
        triage = result.email.triage
        draft = result.email.reply_draft
        payload = {
            "message_id": message.message_id,
            "sender": message.sender,
            "subject": message.subject,
            "received_at": message.received_at.isoformat(),
            "legal_relevant": triage.legal_relevance >= 0.34,
            "triage_confidence": triage.legal_relevance,
            "triage_action": triage.action,
            "case_candidates": list(triage.case_candidates),
            "reply_draft": _draft_text(draft),
            "issues": [
                {"filename": issue.filename, "error_type": issue.error_type, "message": issue.message}
                for issue in result.issues
            ],
            "documents": [
                {
                    "filename": item.attachment_name,
                    "matter_id": item.workflow.match.matter_id if item.workflow.match else None,
                    "fingerprint": item.workflow.extracted.fingerprint,
                    "analysis": _jsonable(item.workflow.analysis),
                }
                for item in result.documents
            ],
        }
        rpc = getattr(self.client, "rpc")
        rpc("persist_email_processing", {"p_payload": json.dumps(payload, ensure_ascii=False)})


def _draft_text(draft: object | None) -> str | None:
    if draft is None:
        return None
    for name in ("body", "text", "content", "draft"):
        value = getattr(draft, name, None)
        if isinstance(value, str):
            return value
    return str(draft)


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return _jsonable(getattr(value, "value"))
    if hasattr(value, "__dict__"):
        return {k: _jsonable(v) for k, v in vars(value).items()}
    return str(value)

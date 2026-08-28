from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

from .inbox import InboxMessage

if TYPE_CHECKING:
    from .email_pipeline import EmailPipelineResult


class ProcessingResultStore(Protocol):
    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None: ...


class InMemoryProcessingResultStore:
    def __init__(self) -> None:
        self.results: dict[str, EmailPipelineResult] = {}

    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None:
        self.results[message.message_id] = result


class SupabaseProcessingResultStore:
    """Persists email results and preserves failed document outcomes."""

    def __init__(self, client: object) -> None:
        self.client = client

    def save(self, message: InboxMessage, result: EmailPipelineResult) -> None:
        triage = result.email.triage
        documents = []
        for item in result.documents:
            documents.append({
                "filename": item.attachment_name,
                "storage_path": item.storage_path,
                "content_type": item.content_type,
                "fingerprint": item.fingerprint,
                "provider": item.provider,
                "attachment_id": item.attachment_id,
                "document_processing_key": _processing_key(item.provider, message.message_id, item.attachment_id),
                "processing_status": item.status.value,
                "processing_error": item.error,
                "matter_id": item.workflow.match.matter_id if item.workflow and item.workflow.match else None,
                "analysis": _jsonable(item.workflow.analysis) if item.workflow else None,
            })
        payload = {
            "message_id": message.message_id,
            "sender": message.sender,
            "subject": message.subject,
            "received_at": message.received_at.isoformat(),
            "legal_relevant": triage.legal_relevance >= 0.34,
            "triage_confidence": triage.legal_relevance,
            "triage_action": triage.action,
            "case_candidates": list(triage.case_candidates),
            "reply_draft": _draft_text(result.email.reply_draft),
            "issues": [{"filename": i.filename, "error_type": i.error_type, "message": i.message} for i in result.issues],
            "documents": documents,
        }
        self.client.rpc("persist_email_processing", {"p_payload": json.dumps(payload, ensure_ascii=False)})


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
        return _jsonable(value.value)
    if hasattr(value, "__dict__"):
        return {k: _jsonable(v) for k, v in vars(value).items()}
    return str(value)


def _processing_key(provider: str, message_id: str, attachment_id: str | None) -> str | None:
    from .source_artifact import source_artifact_identity

    identity = source_artifact_identity(provider, message_id, attachment_id)
    return identity.processing_key if identity else None

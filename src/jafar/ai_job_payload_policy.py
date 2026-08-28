from __future__ import annotations

import json
from typing import Any


MAX_DURABLE_AI_JOB_PAYLOAD_BYTES = 65_536
SENSITIVE_QUEUE_KEYS = frozenset(
    {
        "prompt",
        "text",
        "content",
        "document_text",
        "document_content",
        "email_body",
        "message_body",
        "transcript",
        "raw_document",
        "attachment_bytes",
        "base64",
    }
)


def validate_durable_ai_job_payload(payload: dict[str, Any]) -> None:
    """Keep the durable queue as a reference envelope, not a second legal-document store.

    Jobs should carry IDs, operation metadata, hashes and object-storage references. Raw prompts,
    transcripts, document bodies and message bodies belong in the controlled matter/document
    storage layer and are loaded by the worker only when required.
    """

    if not isinstance(payload, dict):
        raise ValueError("ai_job_payload_must_be_object")
    _reject_sensitive_keys(payload)
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("ai_job_payload_not_json_safe") from exc
    if len(encoded) > MAX_DURABLE_AI_JOB_PAYLOAD_BYTES:
        raise ValueError("ai_job_payload_too_large")


def _reject_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SENSITIVE_QUEUE_KEYS:
                raise ValueError(f"ai_job_sensitive_payload_key_forbidden:{normalized}")
            _reject_sensitive_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_keys(nested)

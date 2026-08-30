from __future__ import annotations

import pytest

from jafar.ai_job_payload_policy import validate_durable_ai_job_payload


def test_reference_only_queue_payload_accepts_ids_hashes_and_storage_refs() -> None:
    validate_durable_ai_job_payload(
        {
            "matter_id": "matter-1",
            "document_id": "doc-1",
            "storage_path": "owner/matter/doc-1.pdf",
            "input_hash": "abc123",
            "routing": {"task": "legal_analysis", "verification": True},
        }
    )


def test_queue_payload_rejects_sensitive_content_keys_recursively() -> None:
    with pytest.raises(ValueError, match="sensitive_payload_key_forbidden:prompt"):
        validate_durable_ai_job_payload({"matter_id": "m1", "prompt": "privileged text"})

    with pytest.raises(ValueError, match="sensitive_payload_key_forbidden:transcript"):
        validate_durable_ai_job_payload(
            {"matter_id": "m1", "nested": {"transcript": "privileged conversation"}}
        )


def test_queue_payload_rejects_large_or_non_json_safe_values() -> None:
    with pytest.raises(ValueError, match="ai_job_payload_too_large"):
        validate_durable_ai_job_payload({"storage_path": "x" * 70_000})

    with pytest.raises(ValueError, match="ai_job_payload_not_json_safe"):
        validate_durable_ai_job_payload({"deadline": object()})

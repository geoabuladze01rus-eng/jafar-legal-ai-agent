from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .telegram_editor import TelegramEditorialDraft
from .telegram_publication import (
    DeliveryState,
    FactCheckResult,
    FactCheckStatus,
    PublicationRisk,
    PublicationStatus,
    RiskLevel,
    SourceEvidence,
    TelegramPublication,
    parse_options_json,
)


@dataclass(frozen=True, slots=True)
class NotionPublicationRecord:
    properties: dict[str, Any]


def publication_to_notion_properties(
    publication: TelegramPublication,
    *,
    editorial: TelegramEditorialDraft | None = None,
) -> dict[str, Any]:
    """Serialize the canonical publication to the exact Notion editorial schema.

    AI-created material remains Review. This serializer never upgrades a status.
    Legacy fields are written only where they keep v2 readable during migration.
    """

    options_json = json.dumps(
        [{"text": option} for option in publication.options],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    correct_ids_json = json.dumps(
        publication.correct_option_ids,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    source_evidence_json = json.dumps(
        [source.model_dump(mode="json") for source in publication.fact_check.sources],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    blockers_json = (
        json.dumps(
            publication.editorial_blockers,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if publication.editorial_blockers
        else ""
    )

    properties: dict[str, Any] = {
        "Name": publication.title or publication.publication_id or "Telegram publication",
        "Status": publication.status.value,
        "Platform": "Telegram",
        "Publication ID": publication.publication_id,
        "Publication Type": publication.publication_type.value,
        "Content": publication.content,
        "Caption": publication.caption or "",
        "CTA": publication.cta or "",
        "Hashtags": " ".join(publication.hashtags),
        "Image Prompt": publication.image_prompt or "",
        "Photo URL": publication.photo_url,
        "Visual Required": _notion_checkbox(publication.visual_required),
        "Visual Asset Key": publication.visual_asset_key or "",
        "Visual Drive File ID": publication.visual_asset_id or "",
        "Visual Category": publication.visual_category,
        "Source Title": publication.source_title or "",
        "Source URL": publication.source_url,
        "Question": publication.question or "",
        "Options JSON": options_json,
        "Correct Option IDs JSON": correct_ids_json,
        "Explanation": publication.explanation or "",
        "Telegram Message ID": publication.telegram_message_id,
        "Last Error": publication.last_error or "",
        "Fact Check Status": publication.fact_check.status.value,
        "Fact Check Notes": publication.fact_check.notes or "",
        "Source Evidence JSON": source_evidence_json,
        "Legal Risk": publication.risk.legal_risk.value,
        "Privacy Risk": publication.risk.privacy_risk.value,
        "Current Case Risk": _notion_checkbox(publication.risk.current_case_risk),
        "Content Fingerprint": publication.content_fingerprint,
        "Delivery State": publication.delivery_state.value,
        "Reconciliation Required": _notion_checkbox(
            publication.delivery_state is DeliveryState.UNCERTAIN
        ),
        "Editorial Blockers": blockers_json,
    }

    properties["Correct Option ID"] = (
        publication.correct_option_ids[0] if len(publication.correct_option_ids) == 1 else None
    )

    if publication.publish_at is not None:
        properties["date:Publish Date:start"] = publication.publish_at.isoformat()
        properties["date:Publish Date:is_datetime"] = 1
    else:
        properties["date:Publish Date:start"] = None
        properties["date:Publish Date:is_datetime"] = 1

    if publication.published_at is not None:
        properties["date:Published At:start"] = publication.published_at.isoformat()
        properties["date:Published At:is_datetime"] = 1
    else:
        properties["date:Published At:start"] = None
        properties["date:Published At:is_datetime"] = 1

    if editorial is not None:
        properties.update(
            {
                "Recommended Publication Type": editorial.recommended_publication_type.value,
                "Author Value Add": editorial.author_value_add or "",
                "Legal Claims JSON": json.dumps(
                    editorial.legal_claims,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
    return properties


def notion_properties_to_publication(fields: dict[str, Any]) -> TelegramPublication:
    """Read both the new v3 fields and the legacy v2 fields from a Notion row."""

    publication_type = str(fields.get("Publication Type") or "text")
    options = parse_options_json(fields.get("Options JSON"))
    correct_ids = _parse_int_list(fields.get("Correct Option IDs JSON"))
    if not correct_ids and fields.get("Correct Option ID") not in (None, ""):
        correct_ids = [int(fields["Correct Option ID"])]

    source_evidence = _parse_source_evidence(fields.get("Source Evidence JSON"))
    fact_status = _parse_fact_status(fields.get("Fact Check Status"))
    fact_check = FactCheckResult(
        status=fact_status,
        sources=source_evidence,
        notes=_optional_text(fields.get("Fact Check Notes")),
    )
    risk = PublicationRisk(
        legal_risk=_parse_risk_level(fields.get("Legal Risk"), fallback=RiskLevel.HIGH),
        privacy_risk=_parse_risk_level(fields.get("Privacy Risk"), fallback=RiskLevel.HIGH),
        current_case_risk=_parse_checkbox(fields.get("Current Case Risk")),
    )
    blockers = _parse_string_list(fields.get("Editorial Blockers"))

    data = {
        "publication_id": _optional_text(fields.get("Publication ID")),
        "publication_type": publication_type,
        "title": _notion_title(fields),
        "content": str(fields.get("Content") or ""),
        "caption": _optional_text(fields.get("Caption")),
        "cta": _optional_text(fields.get("CTA")),
        "hashtags": _parse_hashtags(fields.get("Hashtags")),
        "image_prompt": _optional_text(fields.get("Image Prompt")),
        "photo_url": _optional_text(fields.get("Photo URL")),
        "visual_required": _parse_checkbox(fields.get("Visual Required")),
        "visual_asset_key": _optional_text(fields.get("Visual Asset Key")),
        "visual_asset_id": _optional_text(fields.get("Visual Drive File ID")),
        "visual_category": _optional_text(fields.get("Visual Category")),
        "question": _optional_text(fields.get("Question")),
        "options": options,
        "correct_option_ids": correct_ids,
        "explanation": _optional_text(fields.get("Explanation")),
        "source_title": _optional_text(fields.get("Source Title")),
        "source_url": _optional_text(fields.get("Source URL")),
        "publish_at": _parse_datetime(fields, "Publish Date"),
        "status": _parse_publication_status(fields.get("Status")),
        "telegram_message_id": _optional_int(fields.get("Telegram Message ID")),
        "published_at": _parse_datetime(fields, "Published At"),
        "last_error": _optional_text(fields.get("Last Error")),
        "requires_fact_check": fact_status is not FactCheckStatus.NOT_REQUIRED,
        "fact_check": fact_check,
        "risk": risk,
        "editorial_blockers": blockers,
        "delivery_state": _parse_delivery_state(fields.get("Delivery State")),
    }
    return TelegramPublication.model_validate(data)


def _parse_source_evidence(value: Any) -> list[SourceEvidence]:
    if value in (None, ""):
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Source Evidence JSON must be an array")
    return [SourceEvidence.model_validate(item) for item in parsed]


def _parse_int_list(value: Any) -> list[int]:
    if value in (None, ""):
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Correct Option IDs JSON must be an array")
    return [int(item) for item in parsed]


def _parse_string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Expected a JSON array of strings")
    return parsed


def _parse_hashtags(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [part for part in str(value).split() if part]


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _notion_title(fields: dict[str, Any]) -> str | None:
    """Discard the synthetic Notion title used when the canonical title is empty."""

    title = _optional_text(fields.get("Name"))
    publication_id = _optional_text(fields.get("Publication ID"))
    if title in {publication_id, "Telegram publication"}:
        return None
    return title


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _parse_datetime(fields: dict[str, Any], name: str) -> datetime | None:
    value = fields.get(f"date:{name}:start", fields.get(name))
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_publication_status(value: Any) -> PublicationStatus:
    try:
        return PublicationStatus(str(value or PublicationStatus.REVIEW.value))
    except ValueError:
        return PublicationStatus.REVIEW


def _parse_delivery_state(value: Any) -> DeliveryState:
    try:
        return DeliveryState(str(value or DeliveryState.PENDING.value))
    except ValueError:
        return DeliveryState.UNCERTAIN


def _parse_fact_status(value: Any) -> FactCheckStatus:
    try:
        return FactCheckStatus(str(value or FactCheckStatus.PENDING.value))
    except ValueError:
        return FactCheckStatus.FAILED


def _parse_risk_level(value: Any, *, fallback: RiskLevel) -> RiskLevel:
    try:
        return RiskLevel(str(value or RiskLevel.LOW.value))
    except ValueError:
        return fallback


def _notion_checkbox(value: bool) -> str:
    return "__YES__" if value else "__NO__"


def _parse_checkbox(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).upper() in {"__YES__", "TRUE", "1", "YES"}

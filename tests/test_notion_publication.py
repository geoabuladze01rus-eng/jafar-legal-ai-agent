from __future__ import annotations

import json
from datetime import datetime, timezone

from jafar.notion_publication import (
    notion_properties_to_publication,
    publication_to_notion_properties,
)
from jafar.telegram_editor import TelegramEditorialDraft
from jafar.telegram_publication import (
    DeliveryState,
    FactCheckResult,
    FactCheckStatus,
    PublicationRisk,
    PublicationStatus,
    RiskLevel,
    SourceEvidence,
    TelegramPublication,
)


def test_ai_editorial_record_stays_review_in_notion() -> None:
    publication = TelegramPublication(
        publication_type="text",
        title="Тема",
        content="Материал",
        status="Review",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
    )
    draft = TelegramEditorialDraft(
        title="Тема",
        hook="Хук",
        content="Материал",
        recommended_publication_type="photo",
        author_value_add="Автор объясняет следственную логику.",
        legal_claims=["Норма требует проверки"],
    )

    props = publication_to_notion_properties(publication, editorial=draft)

    assert props["Status"] == "Review"
    assert props["Recommended Publication Type"] == "photo"
    assert props["Author Value Add"] == "Автор объясняет следственную логику."
    assert json.loads(props["Legal Claims JSON"]) == ["Норма требует проверки"]


def test_empty_editorial_blockers_serialize_as_physically_empty_notion_field() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="Материал",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
        editorial_blockers=[],
    )

    props = publication_to_notion_properties(publication)
    restored = notion_properties_to_publication(props)

    assert props["Editorial Blockers"] == ""
    assert restored.editorial_blockers == []


def test_nonempty_editorial_blockers_remain_json_array() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="Материал",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
        editorial_blockers=["incorrect_author_status"],
    )

    props = publication_to_notion_properties(publication)

    assert json.loads(props["Editorial Blockers"]) == ["incorrect_author_status"]


def test_poll_options_are_stored_as_current_input_poll_option_objects() -> None:
    publication = TelegramPublication(
        publication_type="quiz",
        title="Quiz",
        content="Описание",
        question="Вопрос?",
        options=["A", "B"],
        correct_option_ids=[1],
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
    )

    props = publication_to_notion_properties(publication)

    assert json.loads(props["Options JSON"]) == [{"text": "A"}, {"text": "B"}]
    assert json.loads(props["Correct Option IDs JSON"]) == [1]
    assert props["Correct Option ID"] == 1


def test_v3_round_trip_preserves_safety_state() -> None:
    source = SourceEvidence(
        title="Верховный Суд Российской Федерации",
        url="https://vsrf.ru/example",
        authority_rank=2,
        verified=True,
    )
    publication = TelegramPublication(
        publication_type="text",
        title="Тема",
        content="Материал",
        status="Ready",
        publish_at=datetime(2026, 9, 9, 9, 0, tzinfo=timezone.utc),
        requires_fact_check=True,
        fact_check=FactCheckResult(
            status=FactCheckStatus.VERIFIED,
            sources=[source],
            notes="Проверено",
        ),
        risk=PublicationRisk(
            legal_risk=RiskLevel.MEDIUM,
            privacy_risk=RiskLevel.LOW,
            current_case_risk=False,
        ),
        editorial_blockers=["operator_note"],
        delivery_state=DeliveryState.PENDING,
    )

    restored = notion_properties_to_publication(publication_to_notion_properties(publication))

    assert restored.status is PublicationStatus.READY
    assert restored.fact_check.status is FactCheckStatus.VERIFIED
    assert restored.fact_check.sources[0].authority_rank == 2
    assert restored.risk.legal_risk is RiskLevel.MEDIUM
    assert restored.editorial_blockers == ["operator_note"]
    assert restored.content_fingerprint == publication.content_fingerprint


def test_visual_asset_fields_round_trip() -> None:
    publication = TelegramPublication(
        publication_type="photo",
        content="Подпись",
        visual_required=True,
        visual_asset_key="what_to_do:v1",
        visual_asset_id="legacy-drive-file-id",
        visual_category="what_to_do",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
    )

    props = publication_to_notion_properties(publication)
    restored = notion_properties_to_publication(props)

    assert props["Visual Asset Key"] == "what_to_do:v1"
    assert props["Visual Drive File ID"] == "legacy-drive-file-id"
    assert props["Visual Category"] == "what_to_do"
    assert props["Visual Required"] == "__YES__"
    assert restored.visual_asset_key == "what_to_do:v1"
    assert restored.visual_asset_id == "legacy-drive-file-id"
    assert restored.visual_category == "what_to_do"
    assert restored.visual_required is True
    assert restored.content_fingerprint == publication.content_fingerprint


def test_uncertain_delivery_sets_reconciliation_flag() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="Материал",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
        delivery_state=DeliveryState.UNCERTAIN,
    )
    props = publication_to_notion_properties(publication)
    assert props["Delivery State"] == "uncertain"
    assert props["Reconciliation Required"] == "__YES__"


def test_published_at_and_message_id_round_trip() -> None:
    published_at = datetime(2026, 9, 8, 18, 30, tzinfo=timezone.utc)
    publication = TelegramPublication(
        publication_type="text",
        content="Опубликовано",
        status="Published",
        telegram_message_id=77,
        published_at=published_at,
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
        delivery_state=DeliveryState.SENT,
    )

    props = publication_to_notion_properties(publication)
    restored = notion_properties_to_publication(props)

    assert props["date:Published At:start"] == published_at.isoformat()
    assert restored.telegram_message_id == 77
    assert restored.published_at == published_at
    assert restored.delivery_state is DeliveryState.SENT

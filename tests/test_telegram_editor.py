from __future__ import annotations

from datetime import datetime, timezone

from jafar.telegram_editor import (
    EDITOR_SYSTEM_PROMPT,
    TelegramEditorialDraft,
    TelegramEditorialService,
)
from jafar.telegram_publication import PublicationStatus, PublicationType


class FakeEditorialProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.system_prompt = ""
        self.response_model = None

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.system_prompt = system_prompt
        self.response_model = response_model
        return response_model.model_validate(self.payload)


def base_payload(**overrides):
    value = {
        "title": "Что следователь видит в этой ситуации",
        "hook": "⚠️ На бумаге всё выглядит просто. В деле — нет.",
        "recommended_publication_type": "text",
        "content": "🔎 Разбираем процессуальную механику без выдуманных обстоятельств.",
        "author_value_add": "Показываем, как этот эпизод оценивается изнутри следственной логики.",
        "legal_claims": [],
        "risk_flags": [],
    }
    value.update(overrides)
    return value


def test_editor_prompt_fixes_author_status_and_schema_has_no_status() -> None:
    provider = FakeEditorialProvider(base_payload())
    service = TelegramEditorialService(provider)

    result = service.create_publication(topic="Тема", source_text="Подтверждённые факты")

    assert "НЕ адвокат" in provider.system_prompt
    assert "2–5 уместных смысловых эмодзи" in provider.system_prompt
    assert "status" not in TelegramEditorialDraft.model_fields
    assert result.publication.status is PublicationStatus.REVIEW


def test_ai_can_never_approve_publication() -> None:
    provider = FakeEditorialProvider(base_payload())
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Подтверждённые факты",
    )

    assert result.publication.status is PublicationStatus.REVIEW
    assert result.publication.publish_decision().allowed is False
    assert "status_not_ready" in result.publication.publish_decision().reasons


def test_text_draft_does_not_require_visual_asset() -> None:
    provider = FakeEditorialProvider(base_payload(image_prompt="Optional editorial visual concept"))
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
    )

    assert result.publication.publication_type is PublicationType.TEXT
    assert result.publication.visual_required is False
    assert "visual_asset_missing" not in result.publication.editorial_blockers
    assert "visual_category_missing" not in result.publication.editorial_blockers


def test_news_without_author_value_add_gets_machine_blocker() -> None:
    provider = FakeEditorialProvider(base_payload(author_value_add=""))
    result = TelegramEditorialService(provider).create_publication(
        topic="Новость",
        source_text="Подтверждённый инфоповод",
        source_url="https://example.com/source",
        is_news=True,
    )

    assert "missing_author_value_add" in result.publication.editorial_blockers
    result.publication.status = PublicationStatus.READY
    decision = result.publication.publish_decision(now=datetime.now(timezone.utc))
    assert decision.allowed is False
    assert "editorial:missing_author_value_add" in decision.reasons


def test_news_without_source_url_gets_machine_blocker() -> None:
    provider = FakeEditorialProvider(base_payload())
    result = TelegramEditorialService(provider).create_publication(
        topic="Новость",
        source_text="Инфоповод",
        is_news=True,
    )
    assert "news_source_url_missing" in result.publication.editorial_blockers


def test_incorrect_advocate_status_is_blocked() -> None:
    provider = FakeEditorialProvider(
        base_payload(content="🔎 Адвокат Артур Чернов объясняет процессуальную ситуацию. ✅")
    )
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
    )
    assert "incorrect_author_status" in result.publication.editorial_blockers


def test_plain_text_without_emoji_gets_machine_blocker() -> None:
    provider = FakeEditorialProvider(
        base_payload(
            hook="На бумаге всё выглядит просто. В деле — нет.",
            content="Разбираем процессуальную механику без выдуманных обстоятельств.",
        )
    )
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
    )

    assert "telegram_emoji_style_missing" in result.publication.editorial_blockers
    result.publication.status = PublicationStatus.READY
    decision = result.publication.publish_decision(now=datetime.now(timezone.utc))
    assert decision.allowed is False
    assert "editorial:telegram_emoji_style_missing" in decision.reasons


def test_legal_claims_force_pending_fact_check() -> None:
    provider = FakeEditorialProvider(base_payload(legal_claims=["Норма действует с указанной даты"]))
    result = TelegramEditorialService(provider).create_publication(
        topic="Изменение закона",
        source_text="Текст сообщения об изменении",
        source_url="https://publication.pravo.gov.ru/example",
    )
    assert result.publication.requires_fact_check is True
    assert result.publication.fact_check.status.value == "pending"


def test_photo_recommendation_without_asset_stays_valid_review_text() -> None:
    provider = FakeEditorialProvider(
        base_payload(
            recommended_publication_type="photo",
            image_prompt="Cinematic investigator office, no identifiable people",
        )
    )
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
    )
    assert result.draft.recommended_publication_type is PublicationType.PHOTO
    assert result.publication.publication_type is PublicationType.TEXT
    assert result.publication.visual_required is True
    assert "visual_asset_missing" in result.publication.editorial_blockers
    assert "visual_category_missing" in result.publication.editorial_blockers
    assert "photo_asset_missing" in result.publication.editorial_blockers


def test_photo_recommendation_with_approved_asset_key_stays_photo() -> None:
    provider = FakeEditorialProvider(
        base_payload(
            recommended_publication_type="photo",
            image_prompt="Cinematic investigator office, no identifiable people",
        )
    )
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
        visual_asset_key="what_to_do:v1",
        visual_category="what_to_do",
    )

    assert result.publication.publication_type is PublicationType.PHOTO
    assert result.publication.visual_required is True
    assert result.publication.visual_asset_key == "what_to_do:v1"
    assert result.publication.visual_category == "what_to_do"
    assert "visual_asset_missing" not in result.publication.editorial_blockers
    assert "visual_category_missing" not in result.publication.editorial_blockers
    assert "photo_asset_missing" not in result.publication.editorial_blockers


def test_personal_data_is_routed_to_review_risk() -> None:
    provider = FakeEditorialProvider(
        base_payload(content="🔎 Телефон +7 (918) 123-45-67 указан в материале. ✅")
    )
    result = TelegramEditorialService(provider).create_publication(
        topic="Тема",
        source_text="Факт",
    )
    assert result.publication.risk.privacy_risk.value != "low"


def test_recommended_publish_at_must_be_timezone_aware() -> None:
    payload = base_payload(recommended_publish_at="2026-09-09T10:00:00+03:00")
    draft = TelegramEditorialDraft.model_validate(payload)
    assert draft.recommended_publish_at is not None
    assert draft.recommended_publish_at.tzinfo is not None


def test_prompt_constant_contains_editorial_structure() -> None:
    assert "HOOK" in EDITOR_SYSTEM_PROMPT
    assert "author_value_add" in EDITOR_SYSTEM_PROMPT
    assert "approved visual asset" in EDITOR_SYSTEM_PROMPT

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from jafar.telegram_content_risk import TelegramContentRiskGuard
from jafar.telegram_publication import (
    FactCheckResult,
    FactCheckStatus,
    PublicationRisk,
    RiskLevel,
    TelegramPublication,
    parse_options_json,
)


def verified() -> FactCheckResult:
    return FactCheckResult(status=FactCheckStatus.VERIFIED)


def ready_text(**overrides):
    values = {
        "publication_type": "text",
        "content": "Проверенный материал",
        "status": "Ready",
        "fact_check": verified(),
    }
    values.update(overrides)
    return TelegramPublication(**values)


def test_draft_and_review_are_never_publishable() -> None:
    for status in ("Draft", "Review"):
        post = ready_text(status=status)
        decision = post.publish_decision()
        assert decision.allowed is False
        assert "status_not_ready" in decision.reasons


def test_ready_future_date_is_blocked() -> None:
    post = ready_text(publish_at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert post.publish_decision().allowed is False
    assert "publish_time_not_due" in post.publish_decision().reasons


def test_ready_due_verified_text_is_publishable() -> None:
    post = ready_text(publish_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert post.publish_decision().allowed is True
    assert post.telegram_payload(chat_id="@channel")["method"] == "sendMessage"


def test_unverified_fact_check_is_fail_closed() -> None:
    post = ready_text(fact_check=FactCheckResult(status=FactCheckStatus.UNVERIFIED))
    assert post.publish_decision().allowed is False
    assert "fact_check_not_verified" in post.publish_decision().reasons


def test_current_case_risk_is_fail_closed() -> None:
    post = ready_text(risk=PublicationRisk(current_case_risk=True))
    assert post.publish_decision().allowed is False
    assert "current_case_risk" in post.publish_decision().reasons


def test_privacy_risk_is_fail_closed() -> None:
    post = ready_text(risk=PublicationRisk(privacy_risk=RiskLevel.MEDIUM))
    assert post.publish_decision().allowed is False
    assert "privacy_risk_requires_review" in post.publish_decision().reasons


def test_photo_requires_url_or_approved_asset_key() -> None:
    with pytest.raises(ValidationError):
        TelegramPublication(publication_type="photo", content="caption")

    legacy = TelegramPublication(
        publication_type="photo",
        photo_url="https://example.com/image.jpg",
        caption="caption",
        requires_fact_check=False,
    )
    assert legacy.telegram_payload(chat_id="@channel")["photo"] == "https://example.com/image.jpg"


def test_photo_asset_key_requires_resolution_before_send() -> None:
    post = TelegramPublication(
        publication_type="photo",
        visual_required=True,
        visual_asset_key="what_to_do:v1",
        visual_category="what_to_do",
        caption="caption",
        status="Ready",
        fact_check=verified(),
    )

    assert post.publish_decision().allowed is True
    with pytest.raises(ValueError, match="must be resolved"):
        post.telegram_payload(chat_id="@channel")

    media = b"jpeg-bytes"
    payload = post.telegram_payload(chat_id="@channel", resolved_photo=media)
    assert payload["method"] == "sendPhoto"
    assert payload["photo"] == media
    assert payload["caption"] == "caption"


def test_visual_required_is_fail_closed_without_asset_key_or_category() -> None:
    post = TelegramPublication(
        publication_type="photo",
        photo_url="https://example.com/image.jpg",
        visual_required=True,
        status="Ready",
        fact_check=verified(),
    )
    decision = post.publish_decision()
    assert decision.allowed is False
    assert "visual_asset_key_missing" in decision.reasons
    assert "visual_category_missing" in decision.reasons


def test_poll_normalizes_legacy_options_json() -> None:
    assert parse_options_json('["Да", {"text":"Нет"}]') == ["Да", "Нет"]
    post = TelegramPublication(
        publication_type="poll",
        question="Вопрос?",
        options=["Да", "Нет"],
        requires_fact_check=False,
    )
    assert post.telegram_payload(chat_id="@channel")["options"] == [
        {"text": "Да"},
        {"text": "Нет"},
    ]


def test_quiz_uses_current_correct_option_ids_contract() -> None:
    post = TelegramPublication(
        publication_type="quiz",
        question="Вопрос?",
        options=["A", "B"],
        correct_option_ids=[1],
        explanation="Потому что B",
        requires_fact_check=False,
    )
    payload = post.telegram_payload(chat_id="@channel")
    assert payload["type"] == "quiz"
    assert payload["correct_option_ids"] == [1]
    assert "correct_option_id" not in payload


def test_quiz_rejects_out_of_range_answer() -> None:
    with pytest.raises(ValidationError):
        TelegramPublication(
            publication_type="quiz",
            question="Вопрос?",
            options=["A"],
            correct_option_ids=[1],
            requires_fact_check=False,
        )


def test_publication_id_and_fingerprint_are_deterministic() -> None:
    one = TelegramPublication(
        publication_type="text",
        title="Тема",
        content="Материал",
        source_url="https://example.com/source",
        requires_fact_check=False,
    )
    two = TelegramPublication(
        publication_type="text",
        title="  ТЕМА  ",
        content="Материал",
        source_url="https://example.com/source",
        requires_fact_check=False,
    )
    assert one.publication_id == two.publication_id
    assert one.content_fingerprint == two.content_fingerprint


def test_visual_asset_key_changes_content_fingerprint() -> None:
    one = TelegramPublication(
        publication_type="photo",
        visual_asset_key="what_to_do:v1",
        visual_category="what_to_do",
        requires_fact_check=False,
    )
    two = TelegramPublication(
        publication_type="photo",
        visual_asset_key="what_to_do:v2",
        visual_category="what_to_do",
        requires_fact_check=False,
    )
    assert one.content_fingerprint != two.content_fingerprint


def test_risk_guard_detects_and_redacts_personal_data() -> None:
    guard = TelegramContentRiskGuard()
    assessment = guard.assess("Телефон +7 (918) 123-45-67, дело № 123456789")
    assert assessment.requires_human_review is True
    assert assessment.risk.privacy_risk is RiskLevel.HIGH
    redacted = guard.redact("Телефон +7 (918) 123-45-67")
    assert "123-45-67" not in redacted

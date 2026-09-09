from __future__ import annotations

from jafar.notion_publication import (
    notion_properties_to_publication,
    publication_to_notion_properties,
)
from jafar.telegram_publication import FactCheckResult, FactCheckStatus, TelegramPublication


def _verified() -> FactCheckResult:
    return FactCheckResult(status=FactCheckStatus.VERIFIED)


def test_visual_required_text_is_fail_closed_even_with_asset() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="⚠️ Проверенный материал. ✅",
        status="Ready",
        fact_check=_verified(),
        visual_required=True,
        visual_asset_id="drive-file-123",
        visual_category="what_to_do",
    )

    decision = publication.publish_decision()

    assert decision.allowed is False
    assert "visual_required_but_text" in decision.reasons


def test_visual_required_missing_asset_is_fail_closed() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="⚠️ Проверенный материал. ✅",
        status="Ready",
        fact_check=_verified(),
        visual_required=True,
        visual_category="what_to_do",
    )

    decision = publication.publish_decision()

    assert decision.allowed is False
    assert "visual_asset_missing" in decision.reasons


def test_visual_required_missing_category_is_fail_closed() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="⚠️ Проверенный материал. ✅",
        status="Ready",
        fact_check=_verified(),
        visual_required=True,
        visual_asset_id="drive-file-123",
    )

    decision = publication.publish_decision()

    assert decision.allowed is False
    assert "visual_category_missing" in decision.reasons


def test_visual_metadata_round_trips_through_notion_adapter() -> None:
    publication = TelegramPublication(
        publication_type="text",
        content="⚠️ Материал в Review. ✅",
        status="Review",
        requires_fact_check=False,
        fact_check=FactCheckResult(status=FactCheckStatus.NOT_REQUIRED),
        visual_required=True,
        visual_asset_id="1_snczqK2tumDCeWcagL2qLYYQmDk4yAG",
        visual_category="what_to_do",
    )

    props = publication_to_notion_properties(publication)
    restored = notion_properties_to_publication(props)

    assert props["Visual Required"] == "__YES__"
    assert props["Visual Drive File ID"] == "1_snczqK2tumDCeWcagL2qLYYQmDk4yAG"
    assert props["Visual Category"] == "what_to_do"
    assert restored.visual_required is True
    assert restored.visual_asset_id == "1_snczqK2tumDCeWcagL2qLYYQmDk4yAG"
    assert restored.visual_category == "what_to_do"


def test_visual_asset_changes_content_fingerprint() -> None:
    one = TelegramPublication(
        publication_type="text",
        content="⚠️ Один и тот же текст. ✅",
        requires_fact_check=False,
        visual_asset_id="asset-a",
        visual_category="what_to_do",
    )
    two = TelegramPublication(
        publication_type="text",
        content="⚠️ Один и тот же текст. ✅",
        requires_fact_check=False,
        visual_asset_id="asset-b",
        visual_category="what_to_do",
    )

    assert one.content_fingerprint != two.content_fingerprint

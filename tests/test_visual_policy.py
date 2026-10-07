from jafar.editorial_autopost import EditorialRequest
from jafar.visual_policy import (
    VisualCategory,
    VisualTemplate,
    select_visual_decision,
    visual_preflight_score,
)


def test_high_resonance_prefers_verified_documentary_photo() -> None:
    decision = select_visual_decision(
        topic="Резонансное задержание",
        title="Суд избрал меру пресечения",
        is_news=True,
        public_resonance="high",
        documentary_photo_verified=True,
    )
    assert decision.category is VisualCategory.DOCUMENTARY_PHOTO_BRANDED
    assert decision.template is VisualTemplate.RESONANT_CASE
    assert decision.ai_allowed is False


def test_high_resonance_without_photo_uses_honest_editorial_visual() -> None:
    decision = select_visual_decision(
        topic="Резонансное задержание",
        title="Что известно к этому часу",
        is_news=True,
        public_resonance="high",
        documentary_photo_verified=False,
    )
    assert decision.category is VisualCategory.BREAKING
    assert decision.ai_allowed is True
    assert "not a reconstruction" in decision.prompt_prefix


def test_documentary_visual_without_provenance_is_blocked() -> None:
    decision = select_visual_decision(
        topic="Резонансное дело",
        title="Суд",
        is_news=True,
        public_resonance="high",
        documentary_photo_verified=True,
    )
    score, status = visual_preflight_score(
        decision=decision,
        image_present=True,
        image_size_bytes=12000,
        prompt="",
        source_url=None,
        provenance_verified=False,
        ai_generated=False,
    )
    assert score == 0
    assert status == "manual_review"


def test_verified_photo_requires_urls() -> None:
    try:
        EditorialRequest(
            topic="Тест",
            source_text="Материал",
            documentary_photo_verified=True,
        )
    except ValueError as exc:
        assert "requires photo URL and source URL" in str(exc)
    else:
        raise AssertionError("verified photo without source URLs must be rejected")


def test_documentary_photo_url_rejects_private_network() -> None:
    from jafar.editorial_autopost import EditorialAutopostService

    try:
        EditorialAutopostService._validate_public_https_url("https://127.0.0.1/image.jpg")
    except RuntimeError as exc:
        assert "non-public address" in str(exc)
    else:
        raise AssertionError("private network URL must be rejected")

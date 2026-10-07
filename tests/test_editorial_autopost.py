from pathlib import Path

from jafar.editorial_autopost import (
    EditorialAutopostService,
    EditorialBundle,
    EditorialDraft,
    EditorialQueueStore,
    EditorialRequest,
    EditorialRisk,
)


class FakeTextProvider:
    def generate(self, request: EditorialRequest) -> EditorialDraft:
        return EditorialDraft(
            title="Почему «просто поговорить» — не просто разговор",
            hook="Вас зовут без повестки. Кажется, что ничего серьёзного не происходит.",
            body="Сначала нужно понять процессуальный статус и цель разговора.",
            cta=None,
            image_prompt="Пустой коридор следственного отдела, закрытая дверь кабинета.",
            legal_claims=[],
            risk=EditorialRisk.GREEN,
            risk_flags=[],
            author_value_add="Взгляд бывшего следователя на логику происходящего.",
        )


class FakeImageProvider:
    def generate(self, image_prompt: str) -> bytes:
        assert image_prompt
        return b"x" * 12000


def test_service_generates_post_and_visual() -> None:
    service = EditorialAutopostService(FakeTextProvider(), FakeImageProvider())
    request = EditorialRequest(
        topic="Просто поговорить",
        source_text="Безопасный редакционный бриф без текущего дела.",
    )

    bundle = service.generate_bundle(request)

    assert bundle.draft.risk is EditorialRisk.GREEN
    assert len(bundle.image_bytes) == 12000
    assert bundle.draft.visual_score >= 80
    assert bundle.draft.visual_review_status == "approved"
    assert "просто разговор" in bundle.draft.title


def test_queue_store_round_trip(tmp_path: Path) -> None:
    store = EditorialQueueStore(tmp_path / "editorial.sqlite3")
    request = EditorialRequest(topic="Тест", source_text="Исходный материал")
    draft = EditorialDraft(
        title="Заголовок",
        hook="Хук",
        body="Основной текст",
        image_prompt="Кинематографичный кабинет",
        legal_claims=[],
        risk=EditorialRisk.YELLOW,
        risk_flags=["news_requires_review"],
        author_value_add="Авторское объяснение.",
    )
    bundle = EditorialBundle(request=request, draft=draft, image_bytes=b"image")

    created = store.create(bundle)
    loaded = store.get(created.publication_id)

    assert loaded.request == request
    assert loaded.draft == draft
    assert loaded.image_bytes == b"image"
    assert loaded.status == "review"

    rejected = store.set_status(created.publication_id, "rejected")
    assert rejected.status == "rejected"

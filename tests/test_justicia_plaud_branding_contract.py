from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_plaud_branding_is_visible_but_not_claimed_as_active_partnership() -> None:
    models = (ROOT / "apple/JafarApp/JusticiaModels.swift").read_text(encoding="utf-8")
    view = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")

    assert 'case transcription = "Транскрибация × PLAUD"' in models
    assert 'title: "Транскрибация × PLAUD"' in view
    assert "Партнёрство предложено" in view
    assert "Официальная интеграция будет активирована после согласования с PLAUD." in view

    forbidden_claims = (
        "Powered by PLAUD",
        "официальный партнёр PLAUD",
        "официальная интеграция PLAUD",
    )
    for claim in forbidden_claims:
        assert claim not in view

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_beta_feedback_is_manual_and_privacy_first() -> None:
    feedback = (ROOT / "apple/JafarApp/JusticiaBetaFeedbackView.swift").read_text(encoding="utf-8")
    settings = (ROOT / "apple/JafarApp/JusticiaScreens.swift").read_text(encoding="utf-8")

    assert "JusticiaBetaFeedbackView()" in settings
    assert "Ничего не отправляется автоматически." in feedback
    assert "Ручная отправка" in feedback
    assert "Скопировать пакет" in feedback
    assert "URLSession" not in feedback
    assert "http://" not in feedback
    assert "https://" not in feedback


def test_feedback_warns_against_legal_and_secret_data() -> None:
    feedback = (ROOT / "apple/JafarApp/JusticiaBetaFeedbackView.swift").read_text(encoding="utf-8")

    for fragment in (
        "ФИО клиентов",
        "тексты документов",
        "номера дел",
        "аудиозаписи",
        "пароли",
        "токены",
        "конфиденциальные сведения",
    ):
        assert fragment in feedback


def test_feedback_diagnostics_are_content_free_snapshot() -> None:
    snapshot = (ROOT / "apple/JafarApp/JusticiaBetaDiagnosticsSnapshot.swift").read_text(encoding="utf-8")
    feedback = (ROOT / "apple/JafarApp/JusticiaBetaFeedbackView.swift").read_text(encoding="utf-8")
    diagnostics = (ROOT / "apple/JafarApp/JusticiaBetaDiagnosticsView.swift").read_text(encoding="utf-8")

    assert "no matter/document/transcript contents included" in snapshot
    assert "JusticiaBetaDiagnosticsSnapshot.report" in feedback
    assert "JusticiaBetaDiagnosticsSnapshot.report" in diagnostics
    assert "URLSession" not in snapshot

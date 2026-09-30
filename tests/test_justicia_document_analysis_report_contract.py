from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_document_analysis_report_is_manual_and_grounded() -> None:
    screens = (ROOT / "apple/JafarApp/JusticiaLiveScreens.swift").read_text(encoding="utf-8")
    clipboard = (ROOT / "apple/JafarApp/JusticiaClipboard.swift").read_text(encoding="utf-8")

    assert "Скопировать справку" in screens
    assert "copyDocumentAnalysis" in screens
    assert "documentAnalysisReport" in screens
    assert "Риски и слабые места:" in screens
    assert "Ключевые факты:" in screens
    assert "Что требует проверки:" in screens
    assert "Сроки и даты:" in screens
    assert "Технические ссылки на локальные фрагменты:" in screens
    assert "Проверка обязательна" in screens
    assert "JusticiaClipboard.copy" in screens

    assert "NSPasteboard.general.setString" in clipboard or "UIPasteboard.general.string" in clipboard
    assert "URLSession" not in clipboard
    assert "http://" not in clipboard
    assert "https://" not in clipboard

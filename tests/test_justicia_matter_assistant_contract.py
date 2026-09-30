from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_matter_assistant_uses_authenticated_matter_research_endpoint() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    matters = (ROOT / "apple/JafarApp/JusticiaLiveScreens.swift").read_text(encoding="utf-8")

    assert 'path: "/v1/matters/\\(matterID)/research"' in client
    assert "JusticiaLiveMattersView(workspace: workspace, apiClient: apiClient)" in root
    assert "JusticiaMatterAssistantView(" in matters
    assert "apiClient: apiClient" in matters
    assert "documents: workspace.documents" in matters
    assert 'Label("ИИ по делу", systemImage: "sparkles")' in matters


def test_matter_assistant_is_explicitly_matter_scoped_with_citations() -> None:
    assistant = (ROOT / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(encoding="utf-8")

    assert "Контекст ограничен выбранным делом" in assistant
    assert "не должна подмешивать материалы других дел" in assistant
    assert "Источники" in assistant
    assert "Противоречия и пробелы" in assistant
    assert "Результат не заменяет проверку первичных материалов юристом." in assistant


def test_matter_assistant_has_no_direct_external_network_target() -> None:
    assistant = (ROOT / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(encoding="utf-8")

    assert "http://" not in assistant
    assert "https://" not in assistant
    assert "URLSession" not in assistant


def test_matter_assistant_renders_readable_document_citations() -> None:
    assistant = (ROOT / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(encoding="utf-8")

    assert "parseCitation" in assistant
    assert "documentName(for:" in assistant
    assert "Страница \\(parsed.page) · фрагмент \\(parsed.chunk)" in assistant
    assert "documents.first(where:" in assistant
    assert "citation.split(separator:" in assistant

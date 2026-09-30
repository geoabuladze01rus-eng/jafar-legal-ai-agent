from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_desktop_runtime_exposes_local_matter_research_service() -> None:
    main = (ROOT / "src/jafar/main.py").read_text(encoding="utf-8")
    desktop = (ROOT / "src/jafar/desktop_legal_research.py").read_text(encoding="utf-8")

    assert "build_desktop_legal_research_service" in main
    assert "_desktop_legal_research_service" in main
    assert "_legal_research_service_for_matter" in main
    assert "matter_store.get(matter_id)" in main
    assert "OllamaDesktopResearchAnswerProvider" in desktop
    assert "DesktopMatterRAGProvider" in desktop
    assert "context.render()" in desktop
    assert "outside selected Matter" in desktop


def test_swift_matter_assistant_uses_authenticated_local_research_endpoint() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    assistant = (ROOT / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(encoding="utf-8")
    screens = (ROOT / "apple/JafarApp/JusticiaLiveScreens.swift").read_text(encoding="utf-8")

    assert 'path: "/v1/matters/\\(matterID)/research"' in client
    assert "researchSelectedMatter(question:" in client
    assert "JusticiaMatterAssistantView(workspace: workspace)" in screens
    assert "Ответ только по материалам выбранного дела" in assistant
    assert "Помощник не использует материалы других дел" in assistant
    assert "workspace.researchCitations" in assistant
    assert "workspace.researchRetrievedChunks" in assistant
    assert "https://" not in assistant


def test_matter_assistant_refuses_empty_corpus_in_ui() -> None:
    assistant = (ROOT / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(encoding="utf-8")

    assert "if workspace.documents.isEmpty" in assistant
    assert "не будет придумывать ответ без материалов" in assistant
    assert "workspace.documents.isEmpty" in assistant

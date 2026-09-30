from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_stored_document_analysis_is_matter_scoped_and_local() -> None:
    main = (ROOT / "src/jafar/main.py").read_text(encoding="utf-8")

    assert '"/v1/matters/{matter_id}/documents/{document_id}/analyze"' in main
    assert "desktop_corpus_store.get_document(matter_id, document_id)" in main
    assert "desktop_corpus_store.read_original(matter_id, document_id)" in main
    assert "matter_store.get(matter_id)" in main
    assert "document_workflow.process(" in main
    assert "matter_id=matter_id" in main


def test_swift_analysis_client_uses_authenticated_loopback_workspace_client() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")

    assert 'path: "/v1/matters/\\(matterID)/documents/\\(documentID)/analyze"' in client
    assert 'method: "POST"' in client
    assert "JusticiaAnalyzeStoredDocumentRequest" in client
    assert "documentAnalysis" in client
    assert "analysisDocumentID" in client
    assert "URLSession" in client
    assert "https://" not in client


def test_documents_ui_exposes_structured_local_analysis() -> None:
    screens = (ROOT / "apple/JafarApp/JusticiaLiveScreens.swift").read_text(encoding="utf-8")

    assert 'Label("Анализировать", systemImage: "sparkles")' in screens
    assert 'Text("Общий вывод")' not in screens  # rendered through analysisSection helper
    assert 'analysisSection("Общий вывод")' in screens
    assert 'analysisSection("Риски и слабые места")' in screens
    assert 'analysisSection("Ключевые факты")' in screens
    assert 'analysisSection("Что требует проверки")' in screens
    assert 'analysisSection("Сроки и даты")' in screens
    assert "локальный ИИ анализирует документ" in screens.lower()
    assert "проверьте факты, нормы и источники" in screens.lower()


def test_analysis_does_not_silently_persist_deadlines_or_events() -> None:
    workflow = (ROOT / "src/jafar/document_workflow.py").read_text(encoding="utf-8")

    assert "Read-only document analysis" in workflow
    assert "event=None" in workflow

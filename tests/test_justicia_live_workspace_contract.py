from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_desktop_workspace_client_is_bound_to_authenticated_loopback() -> None:
    runtime = (ROOT / "apple/JafarApp/BackendRuntime.swift").read_text(encoding="utf-8")
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")

    assert 'baseURL = URL(string: "http://127.0.0.1:\\(port)")' in runtime
    assert "JusticiaAPIClient(baseURL: baseURL, token: token)" in runtime
    assert 'urlRequest.setValue("Bearer \\(token)", forHTTPHeaderField: "Authorization")' in client
    assert "https://" not in client


def test_live_workspace_uses_real_matter_and_document_endpoints() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")

    assert 'path: "/v1/matters"' in client
    assert '"/v1/matters/\\(matterID)/documents"' in client
    assert '"/v1/matters/\\(matterID)/documents/import"' in client
    assert "JusticiaLiveHomeView(workspace: workspace" in root
    assert "JusticiaLiveMattersView(workspace: workspace)" in root
    assert "JusticiaLiveDocumentsView(workspace: workspace)" in root


def test_document_import_uses_security_scoped_file_access() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")

    assert "startAccessingSecurityScopedResource()" in client
    assert "stopAccessingSecurityScopedResource()" in client
    assert '"multipart/form-data; boundary=\\(boundary)"' in client


def test_global_search_is_local_and_bound_to_workspace_data() -> None:
    search = (ROOT / "apple/JafarApp/JusticiaGlobalSearchView.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")

    assert "workspace.matters.filter" in search
    assert "workspace.documents.filter" in search
    assert "JusticiaSection.allCases.filter" in search
    assert "https://" not in search
    assert "не отправляет запрос в облако" in search
    assert "JusticiaGlobalSearchView(" in root
    assert "showingSearchResults = true" in root

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_workspace_search_and_templates_are_live_ui_surfaces() -> None:
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    search = (ROOT / "apple/JafarApp/JusticiaGlobalSearchView.swift").read_text(encoding="utf-8")
    templates = (ROOT / "apple/JafarApp/JusticiaTemplatesWorkspaceView.swift").read_text(encoding="utf-8")

    assert "JusticiaGlobalSearchView(" in root
    assert "JusticiaTemplatesWorkspaceView()" in root
    assert "workspace.matters.filter" in search
    assert "workspace.documents.filter" in search
    assert "filteredTemplates" in templates
    assert "Скопировать" in templates


def test_comfort_preferences_are_persistent_and_consumed_by_shell() -> None:
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    screens = (ROOT / "apple/JafarApp/JusticiaScreens.swift").read_text(encoding="utf-8")

    for key in (
        "justicia.compactSidebar",
        "justicia.notifications",
        "justicia.reduceMotion",
    ):
        assert key in root
        assert key in screens

    assert "compactSidebar ? 78 : JusticiaTheme.sidebarWidth" in root
    assert "if notificationsEnabled" in root
    assert "reduceMotion ? nil" in root
    assert "Эти настройки сохраняются на этом устройстве." in screens

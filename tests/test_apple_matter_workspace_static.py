from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apple" / "JafarApp"


def test_matter_detail_client_is_authenticated_and_read_only() -> None:
    source = (APP / "Networking" / "MatterDetailAPI.swift").read_text(encoding="utf-8")

    assert 'appendingPathComponent("v1/matters")' in source
    assert 'appendingPathComponent("events")' in source
    assert 'request.httpMethod = "GET"' in source
    assert 'forHTTPHeaderField: "Authorization"' in source
    assert "POST" not in source
    assert "PUT" not in source
    assert "PATCH" not in source
    assert "DELETE" not in source


def test_matter_workspace_exposes_deadlines_timeline_and_provenance_boundary() -> None:
    source = (APP / "UI" / "MatterNavigatorView.swift").read_text(encoding="utf-8")

    assert "Карточка дела" in source
    assert "Сроки" in source
    assert "Хронология" in source
    assert "Уверенность извлечения" in source
    assert "Анализ документов не изменяет карточку" in source
    assert "sourceDocument" in source


def test_connected_root_exposes_direct_cases_entrypoint() -> None:
    source = (APP / "UI" / "ConnectedRootView.swift").read_text(encoding="utf-8")

    assert "showingMatterNavigator" in source
    assert "MatterNavigatorView" in source
    assert 'systemName: "briefcase.fill"' in source
    assert 'accessibilityLabel("Открыть дела")' in source

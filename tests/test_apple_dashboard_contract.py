from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLE = ROOT / "apple" / "JafarApp"


def read(relative: str) -> str:
    return (APPLE / relative).read_text(encoding="utf-8")


def test_app_uses_connected_root_and_live_dashboard() -> None:
    app = read("JafarApp.swift")
    root = read("UI/ConnectedRootView.swift")

    assert "ConnectedRootView()" in app
    assert "LiveDashboardView(dashboard: dashboard)" in root
    assert "JafarConnectionSettingsView" in root
    assert "JafarAlertsStore.shared.replace" in root


def test_api_token_is_keychain_backed_not_written_to_user_defaults() -> None:
    api = read("Networking/JafarAPI.swift")

    assert "import Security" in api
    assert "kSecClassGenericPassword" in api
    assert "SecItemAdd" in api
    assert "SecItemUpdate" in api
    assert "SecItemDelete" in api
    assert "UserDefaults.standard.set(normalizedToken" not in api
    assert '"JAFAR_API_TOKEN"' in api


def test_connection_ui_uses_secure_field_and_https_validation() -> None:
    settings = read("UI/JafarConnectionSettingsView.swift")

    assert "SecureField" in settings
    assert "Проверить подключение" in settings
    assert 'scheme == "https"' in settings
    assert 'scheme == "http" && localHosts.contains(host)' in settings
    assert "JafarAPIConfiguration.save" in settings


def test_dashboard_client_uses_bearer_header_and_real_dashboard_endpoint() -> None:
    api = read("Networking/JafarAPI.swift")
    command = read("Voice/CommandClient.swift")

    assert 'forHTTPHeaderField: "Authorization"' in api
    assert 'appendingPathComponent("v1/dashboard")' in api
    assert 'forHTTPHeaderField: "Authorization"' in command
    assert 'appendingPathComponent("v1/command")' in command


def test_live_dashboard_surfaces_matters_deadlines_and_approval_counts() -> None:
    view = read("UI/LiveDashboardView.swift")

    assert "dashboard.snapshot.activeMatters" in view
    assert "dashboard.snapshot.overdueDeadlines" in view
    assert "dashboard.snapshot.deadlinesNext7Days" in view
    assert "dashboard.snapshot.pendingApprovals" in view
    assert "dashboard.snapshot.matters" in view
    assert "dashboard.snapshot.signals" in view

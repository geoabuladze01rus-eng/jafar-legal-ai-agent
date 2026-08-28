from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apple" / "JafarApp"


def test_approval_api_uses_authenticated_backend_queue() -> None:
    source = (APP / "Networking" / "ApprovalAPI.swift").read_text(encoding="utf-8")

    assert "v1/approvals" in source
    assert 'operation: "approve"' in source
    assert 'operation: "reject"' in source
    assert 'forHTTPHeaderField: "Authorization"' in source
    assert "JafarApprovalIdentity" in source
    assert "LocalApprovalClient" in source


def test_live_dashboard_requires_explicit_human_decision() -> None:
    source = (APP / "UI" / "LiveDashboardView.swift").read_text(encoding="utf-8")

    assert "На одобрение адвоката" in source
    assert "Одобрить действие" in source
    assert "ApprovalRejectionSheet" in source
    assert "Причина сохраняется в журнале решения" in source
    assert "само по себе не отправит" in source
    assert "JafarApprovalIdentity.value.isEmpty" in source
    assert "let decisionDisabled = JafarApprovalIdentity.value.isEmpty" in source
    assert source.count(".disabled(decisionDisabled)") == 2


def test_connection_settings_capture_auditable_approver_identity() -> None:
    source = (APP / "UI" / "JafarConnectionSettingsView.swift").read_text(
        encoding="utf-8"
    )

    assert "Имя или ID адвоката" in source
    assert "JafarApprovalIdentity.save" in source
    assert "API token хранится в Keychain" in source
    assert "Одобрение не означает автоматическую отправку" in source

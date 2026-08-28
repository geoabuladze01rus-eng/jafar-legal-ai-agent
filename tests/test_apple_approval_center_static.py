from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apple" / "JafarApp"


def test_approval_api_uses_authenticated_backend_queue_without_client_identity() -> None:
    source = (APP / "Networking" / "ApprovalAPI.swift").read_text(encoding="utf-8")

    assert "v1/approvals" in source
    assert 'operation: "approve"' in source
    assert 'operation: "reject"' in source
    assert 'forHTTPHeaderField: "Authorization"' in source
    assert "JafarApprovalIdentity" not in source
    assert "let approver" not in source
    assert "LocalApprovalClient" in source
    assert "fetchApprovedAwaitingExecution" in source
    assert 'fetch(state: "approved")' in source


def test_live_dashboard_requires_explicit_human_decision() -> None:
    source = (APP / "UI" / "LiveDashboardView.swift").read_text(encoding="utf-8")

    assert "На одобрение адвоката" in source
    assert "Одобрить действие" in source
    assert "ApprovalRejectionSheet" in source
    assert "Причина сохраняется в журнале решения" in source
    assert "по себе не отправит" in source
    assert "задаётся на backend" in source
    assert "JafarApprovalIdentity" not in source
    assert source.count(".disabled(decisionDisabled)") == 2


def test_live_dashboard_distinguishes_approval_from_execution() -> None:
    source = (APP / "UI" / "LiveDashboardView.swift").read_text(encoding="utf-8")

    assert "approvedAwaitingExecutionCenter" in source
    assert "Одобрено — ожидает выполнения" in source
    assert "Одобрение и фактическое выполнение намеренно разделены" in source
    assert "НЕ ВЫПОЛНЕНО" in source
    assert "execution step" in source


def test_connection_settings_explain_server_controlled_audit_identity() -> None:
    source = (APP / "UI" / "JafarConnectionSettingsView.swift").read_text(
        encoding="utf-8"
    )

    assert "Личность адвоката для журнала одобрений задаётся на backend" in source
    assert "JafarApprovalIdentity.save" not in source
    assert "API token хранится в Keychain" in source
    assert "Audit identity контролируется сервером" in source
    assert "Одобрение не означает автоматическую отправку" in source

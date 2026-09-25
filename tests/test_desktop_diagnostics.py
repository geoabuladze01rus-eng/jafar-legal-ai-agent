from jafar.desktop_diagnostics import DesktopDiagnostic, redact_diagnostic
from jafar.license_state import LicenseState, license_can_authorize_matter_access


def test_diagnostics_redact_token_like_values_and_do_not_require_matter_content():
    assert "secret-value" not in redact_diagnostic("Bearer secret-value")
    report = DesktopDiagnostic("2.1.0b1", "ready", "ready", "local", "qwen3:4b").render()
    assert "Local storage: ready" in report
    assert "Bearer" not in report


def test_license_state_cannot_authorize_matters_or_bypass_security_boundaries():
    assert license_can_authorize_matter_access(LicenseState.ACTIVE) is False

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_justice_ui_has_explicit_demo_boundary() -> None:
    source = (ROOT / "apple/JafarApp/UI/JusticeWorkspaceView.swift").read_text()
    assert 'AppStorage("justice.demo_mode")' in source
    assert "demoMode ? JusticeSamples.matters : dashboard.snapshot.matters" in source
    assert "JusticeSamples" in source


def test_onboarding_is_local_and_brand_safe() -> None:
    source = (ROOT / "apple/JafarApp/UI/JusticeOnboardingView.swift").read_text()
    assert 'AppStorage("justice.onboarding_completed")' in source
    assert "ЮСТИЦИЯ AI" in source
    assert "JAFAR" not in source

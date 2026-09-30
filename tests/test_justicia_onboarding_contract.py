from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_first_run_onboarding_is_persistent_and_reopenable() -> None:
    onboarding = (ROOT / "apple/JafarApp/JusticiaOnboardingView.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    settings = (ROOT / "apple/JafarApp/JusticiaScreens.swift").read_text(encoding="utf-8")

    assert '@AppStorage("justicia.onboardingCompleted")' in onboarding
    assert '@AppStorage("justicia.onboardingCompleted")' in root
    assert '@AppStorage("justicia.onboardingCompleted")' in settings
    assert "JusticiaOnboardingView()" in root
    assert "if !onboardingCompleted" in root
    assert 'Button("Показать снова")' in settings
    assert "onboardingCompleted = false" in settings
    assert "onboardingCompleted = true" in onboarding


def test_onboarding_explains_local_privacy_and_plaud_boundary() -> None:
    onboarding = (ROOT / "apple/JafarApp/JusticiaOnboardingView.swift").read_text(encoding="utf-8")

    assert "Конфиденциальность по умолчанию" in onboarding
    assert "Без автоматического облака" in onboarding
    assert "qwen3:4b" in onboarding
    assert "Транскрибация × PLAUD" in onboarding
    assert "предлагаемое партнёрство" in onboarding
    assert "после согласования с PLAUD" in onboarding
    assert "On-device распознавание" in onboarding

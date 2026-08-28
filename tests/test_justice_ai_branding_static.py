from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apple" / "JafarApp"


def test_public_apple_brand_is_justice_ai_while_internal_engine_stays_jafar() -> None:
    content = (APP / "ContentView.swift").read_text(encoding="utf-8")
    plist = (APP / "Info.plist").read_text(encoding="utf-8")
    project = (ROOT / "apple" / "project.yml").read_text(encoding="utf-8")

    assert 'Text("ЮСТИЦИЯ AI")' in content
    assert 'Text("Интеллектуальная система адвоката")' in content
    assert "<string>ЮСТИЦИЯ AI</string>" in plist
    assert 'INFOPLIST_KEY_CFBundleDisplayName: "ЮСТИЦИЯ AI"' in project
    assert "PRODUCT_NAME: Jafar" in project


def test_justice_presence_exposes_calm_analysis_and_control_states() -> None:
    source = (APP / "UI" / "JusticePresenceView.swift").read_text(encoding="utf-8")
    content = (APP / "ContentView.swift").read_text(encoding="utf-8")

    assert "enum JusticePresenceState" in source
    assert "case calm" in source
    assert "case analyzing" in source
    assert "case control" in source
    assert "repeatForever" in source
    assert 'return "Требуется решение"' in source
    assert "JusticePresenceView(state: justiceState" in content
    assert "if voice.errorMessage != nil { return .control }" in content
    assert "if voice.isListening || voice.isSpeaking { return .analyzing }" in content


def test_permission_copy_uses_public_brand_not_internal_codename() -> None:
    plist = (APP / "Info.plist").read_text(encoding="utf-8")
    project = (ROOT / "apple" / "project.yml").read_text(encoding="utf-8")

    assert "ЮСТИЦИЯ AI использует микрофон" in plist
    assert "ЮСТИЦИЯ AI использует распознавание речи" in plist
    assert "ЮСТИЦИЯ AI использует Face ID" in plist
    assert "Джафар использует" not in plist
    assert "Джафар использует" not in project

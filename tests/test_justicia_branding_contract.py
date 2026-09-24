from pathlib import Path


ROOT = Path(__file__).parents[1]

USER_VISIBLE_APP_SOURCES = (
    "apple/JafarApp/ContentView.swift",
    "apple/JafarApp/JusticiaRootView.swift",
    "apple/JafarApp/JusticiaScreens.swift",
    "apple/JafarApp/JusticiaTheme.swift",
    "apple/JafarApp/LocalAIStatus.swift",
    "apple/JafarApp/Voice/JafarVoiceIntent.swift",
    "apple/JafarApp/Voice/CommandClient.swift",
)


def test_user_visible_apple_ui_uses_justicia_brand_only() -> None:
    for relative in USER_VISIBLE_APP_SOURCES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "Джафар" not in source
        assert '"JAFAR"' not in source

    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    assert 'Text("Юстиция")' in root
    assert 'Text("ИИ-помощник юриста")' in root


def test_apple_metadata_displays_justicia() -> None:
    project = (ROOT / "apple/project.yml").read_text(encoding="utf-8")
    plist = (ROOT / "apple/JafarApp/Info.plist").read_text(encoding="utf-8")

    assert 'CFBundleDisplayName: "Юстиция"' in project
    assert 'CFBundleName: "Юстиция"' in project
    assert "<string>Юстиция</string>" in plist
    assert "Джафар" not in project
    assert "Джафар" not in plist


def test_customer_facing_macos_package_is_named_justicia() -> None:
    build = (ROOT / "scripts/build_macos_release.sh").read_text(encoding="utf-8")
    distribution = (ROOT / "scripts/package_macos_distribution.sh").read_text(encoding="utf-8")
    notarization = (ROOT / "scripts/notarize_macos_release.sh").read_text(encoding="utf-8")

    assert 'APP_NAME="Юстиция.app"' in build
    assert 'DMG_NAME="Юстиция-${PACKAGE_VERSION}-macos-${ARCH}.dmg"' in build
    assert '-volname "Юстиция ${PACKAGE_VERSION}"' in build
    assert 'APP_PATH="$DIST_DIR/Юстиция.app"' in distribution
    assert "Юстиция.app" in notarization

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_macos_packaging_script_is_fail_closed_and_unsigned_by_default() -> None:
    script = (ROOT / "scripts/build_macos_release.sh").read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "CODE_SIGNING_ALLOWED=NO" in script
    assert "JAFAR_PACKAGE_VERSION" in script
    assert "hdiutil create" in script
    assert "shasum -a 256" in script
    assert "forbidden credential or repository artifact" in script
    assert "build_macos_backend.sh" in script
    assert "Contents/Resources/Helpers" in script
    assert '"$HELPERS_DIR/JafarBackend"' in script


def test_notarization_script_requires_developer_id_and_stored_profile() -> None:
    script = (ROOT / "scripts/notarize_macos_release.sh").read_text(encoding="utf-8")

    assert "Developer ID Application" in script
    assert "NOTARY_PROFILE" in script
    assert "notarytool" not in script or "No submission was performed" in script


def test_packaging_ci_does_not_request_signing_secrets() -> None:
    workflow = (ROOT / ".github/workflows/macos-packaging.yml").read_text(encoding="utf-8")

    assert "macos-15" in workflow
    assert "build_macos_release.sh" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "secrets." not in workflow


def test_generated_apple_metadata_has_release_and_runtime_contract() -> None:
    project = (ROOT / "apple/project.yml").read_text(encoding="utf-8")
    plist = (ROOT / "apple/JafarApp/Info.plist").read_text(encoding="utf-8")

    assert 'CFBundleShortVersionString: "2.1.0"' in project
    assert 'LSMinimumSystemVersion: "14.0"' in project
    assert 'ENABLE_HARDENED_RUNTIME: "YES"' in project
    assert "CFBundleDisplayName" in plist
    assert "NSMicrophoneUsageDescription" in plist
    assert "NSSpeechRecognitionUsageDescription" in plist


def test_packaging_output_is_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "dist/" in gitignore
    assert "apple/JafarApp.xcodeproj/" in gitignore


def test_mac_local_ai_onboarding_is_loopback_only_and_has_safe_states() -> None:
    source = (ROOT / "apple/JafarApp/LocalAIStatus.swift").read_text(encoding="utf-8")

    assert "127.0.0.1:11434" in source
    assert "qwen3:4b" in source
    assert "LOCAL AI READY" in source
    assert "OLLAMA NOT RUNNING" in source
    assert "QWEN3:4B MODEL MISSING" in source
    assert "https://" not in source


def test_backend_packaging_is_one_folder_arm64_and_scans_artifacts() -> None:
    script = (ROOT / "scripts/build_macos_backend.sh").read_text(encoding="utf-8")
    decision = (ROOT / "docs/MACOS_BACKEND_PACKAGING_DECISION.md").read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "--onedir" in script
    assert "Python 3.12 is required" in script
    assert "only Apple Silicon arm64" in script
    assert "JAFAR_DESKTOP_IPC_TOKEN" not in script
    assert "runtime-manifest.sha256" in script
    assert "PyInstaller one-folder sidecar" in decision
    assert (ROOT / "docs/MACOS_BACKEND_RUNTIME_MAP.md").is_file()


def test_swift_supervisor_has_no_shell_and_uses_ephemeral_ipc() -> None:
    source = (ROOT / "apple/JafarApp/BackendRuntime.swift").read_text(encoding="utf-8")

    assert "Helpers/JafarBackend/JafarBackend" in source
    assert "JAFAR_DESKTOP_IPC_TOKEN" in source
    assert "127.0.0.1" in source
    assert "/bin/sh" not in source
    assert "Process()" in source
    assert "onUnexpectedTermination" in source
    assert "JAFAR_DESKTOP_PARENT_PID" in source
    assert "let token = try randomToken()" in source
    assert "SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess" in source
    assert "randomnessUnavailable" in source


def test_distribution_dry_run_builds_then_fails_closed_without_identity() -> None:
    script = (ROOT / "scripts/package_macos_distribution.sh").read_text(encoding="utf-8")

    assert "build_macos_release.sh" in script
    assert "Nested executable inventory" in script
    assert "Developer ID Application identity is unavailable" in script
    assert "notarization was attempted" in script

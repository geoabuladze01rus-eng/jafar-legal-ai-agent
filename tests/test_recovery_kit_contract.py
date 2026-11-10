"""Safety contract for the macOS Keychain recovery beta (no real credentials)."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOL = (ROOT / "scripts/jafar_key_recovery.swift").read_text(encoding="utf-8")
KEY = (ROOT / "apple/JafarApp/DesktopStorageKey.swift").read_text(encoding="utf-8")
WORKFLOW = (
    ROOT / ".github/workflows/keychain-recovery-macos.yml"
).read_text(encoding="utf-8")


def test_cli_contains_only_explicit_key_export_and_import():
    assert 'args == ["self-test"]' in TOOL
    assert 'args == ["status"]' in TOOL
    assert '(command == "export" && args[1] == "--output")' in TOOL
    assert '(command == "import" && args[1] == "--input")' in TOOL
    assert "guard isatty(STDIN_FILENO) == 1" in TOOL
    assert "kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly" in TOOL
    assert "try verifyAgainstExistingArchive(data)" in TOOL
    assert "SQLITE_OPEN_READONLY" in TOOL
    assert "jafar-desktop-matter-storage-v1" in TOOL
    assert "jafar-desktop-corpus-storage-v1" in TOOL
    assert "jafar-desktop-storage-check-v1" in TOOL
    assert "jafar-desktop-corpus-check-v1" in TOOL
    assert "SecItemAdd(query as CFDictionary, nil)" in TOOL
    assert "SecItemUpdate" not in TOOL
    assert "SecItemDelete" not in TOOL
    assert "kSecAttrSynchronizable" not in TOOL
    assert "print(master)" not in TOOL
    assert "print(masterKey)" not in TOOL


def test_recovery_kit_has_a_separate_password_and_authenticated_crypto():
    assert "600_000" in TOOL
    assert "PBKDF2-HMAC-SHA256" in TOOL
    assert "AES.GCM.seal" in TOOL
    assert "AES.GCM.open" in TOOL
    assert "randomBytes(16)" in TOOL
    assert "randomBytes(32)" in TOOL
    assert "authenticating: aad" in TOOL
    assert 'let confirmation = try askSecret("Confirm recovery passphrase: ")' in TOOL
    assert "guard password == confirmation" in TOOL
    assert "guard fsync(fd) == 0" in TOOL
    assert "O_EXCL | O_NOFOLLOW" in TOOL
    assert "LOCK_EX | LOCK_NB" in TOOL


def test_missing_key_does_not_generate_replacement_for_existing_archive():
    assert "existingEncryptedArchiveRequiresRecovery" in KEY
    assert "guard !hasExistingEncryptedArchive() else" in KEY
    assert "matters.sqlite3" in KEY
    assert "corpus.sqlite3" in KEY
    assert "drafts.sqlite3" in KEY
    assert "claim-review-decisions.sqlite3" in KEY
    assert 'pathExtension == "jafarblob"' in KEY
    assert KEY.index("guard !hasExistingEncryptedArchive()") < KEY.index(
        "SecRandomCopyBytes"
    )


def test_macos_workflow_runs_synthetic_only_no_secret_store():
    assert "runs-on: macos-15" in WORKFLOW
    assert "swiftc -o" in WORKFLOW
    assert "self-test" in WORKFLOW
    assert "Recovery codec and archive key preflight self-tests passed" in TOOL
    assert "must-not-exist.json" in WORKFLOW
    assert "SecItemAdd" not in WORKFLOW
    assert "import --input" not in WORKFLOW

"""Offline encrypted backup and non-destructive restore for the macOS JAFAR beta.

Run ONLY when the app and its sidecar are closed. The existing Matter flock
enforces that requirement. A separate passphrase encrypts every archive member.
Source databases and original encrypted blobs are never overwritten.
"""

from __future__ import annotations

import argparse
import fcntl
import getpass
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


FORMAT = "JAFAR-OFFLINE-BACKUP"
VERSION = 1
HEADER = "header.json"
MANIFEST = "manifest.enc"
OBJECTS = "objects/"
DATABASES = (
    "matters.sqlite3",
    "corpus.sqlite3",
    "drafts.sqlite3",
    "claim-review-decisions.sqlite3",
)
MANDATORY_DATABASES = ("matters.sqlite3", "corpus.sqlite3")
MAX_MEMBERS = 10_000
MAX_MEMBER_SIZE = 256 * 1024 * 1024
MAX_MANIFEST_SIZE = 2 * 1024 * 1024
MAX_TOTAL_SIZE = 8 * 1024 * 1024 * 1024
DOC_RE = re.compile(r"documents/[0-9a-f]{32}\.jafarblob\Z")
BLOB_MAGIC = b"JAFARBLOB1"
AAD_PREFIX = b"JAFAR-BACKUP-V1:"
SALT_BYTES = 16


class BackupError(RuntimeError):
    pass


def _ensure_real_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise BackupError("Required encrypted source file is missing or a symlink")
    if path.stat().st_size > MAX_MEMBER_SIZE:
        raise BackupError("Encrypted source file exceeds supported beta backup size")


def _check_new_target(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise BackupError("Destination already exists; overwriting is forbidden")


def _ensure_safe_parent(path: Path) -> None:
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise BackupError("Destination parent must be an existing real directory")


def _check_not_below(path: Path, source: Path) -> None:
    if path.resolve(strict=False).is_relative_to(source.resolve(strict=True)):
        raise BackupError("Destination cannot be inside the live JAFAR data directory")


def _allowed(name: str) -> bool:
    return name in DATABASES or DOC_RE.fullmatch(name) is not None


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase:
        raise BackupError("Backup passphrase is required")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def _encrypt(key: bytes, data: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def _decrypt(key: bytes, data: bytes, aad: bytes) -> bytes:
    if len(data) < 29:
        raise BackupError("Backup member is truncated")
    try:
        return AESGCM(key).decrypt(data[:12], data[12:], aad)
    except (ValueError, TypeError) as exc:
        raise BackupError("Backup authentication failed") from exc
    except Exception as exc:
        # Never return partial plaintext or disclose key material on auth failure.
        raise BackupError("Backup authentication failed") from exc


@contextmanager
def _offline_lock(home: Path) -> Iterator[None]:
    if home.is_symlink() or not home.is_dir():
        raise BackupError("Existing local JAFAR data directory is required")
    handle = None
    try:
        path = home / "matters.lock"
        if path.is_symlink():
            raise BackupError("Invalid Matter lock path")
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        handle = os.fdopen(fd, "r+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupError("Close JAFAR before creating a backup") from exc
        yield
    finally:
        if handle is not None:
            handle.close()


def _sqlite_check(path: Path) -> None:
    _ensure_real_file(path)
    uri = "file:" + quote(str(path.resolve(strict=True)), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as db:
            check = db.execute("PRAGMA quick_check").fetchall()
            if check != [("ok",)]:
                raise BackupError("SQLite snapshot failed integrity check")
    except sqlite3.DatabaseError as exc:
        raise BackupError("Invalid or damaged encrypted database") from exc


def _snapshot_database(source: Path, target: Path) -> None:
    _ensure_real_file(source)
    src_uri = "file:" + quote(str(source.resolve(strict=True)), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(src_uri, uri=True, timeout=5) as db:
            with sqlite3.connect(target) as snapshot:
                db.backup(snapshot)
        os.chmod(target, 0o600)
        _sqlite_check(target)
    except sqlite3.DatabaseError as exc:
        raise BackupError("Failed to snapshot local SQLite database") from exc


def _listed_originals(corpus_snapshot: Path) -> list[str]:
    uri = "file:" + quote(str(corpus_snapshot.resolve(strict=True)), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as db:
            rows = db.execute("SELECT id FROM documents ORDER BY id").fetchall()
    except sqlite3.DatabaseError as exc:
        raise BackupError("Cannot inspect encrypted corpus index") from exc
    names = ["documents/" + str(row[0]) + ".jafarblob" for row in rows]
    if len(names) != len(set(names)) or any(not DOC_RE.fullmatch(n) for n in names):
        raise BackupError("Invalid or duplicated original document identifier")
    return names


def _validate_bundle_tree(root: Path, names: set[str]) -> None:
    if not set(MANDATORY_DATABASES).issubset(names):
        raise BackupError("A Matter or corpus database is missing")
    for name in names:
        if not _allowed(name):
            raise BackupError("Archive contains an unrecognized source path")
    for database in DATABASES:
        if database in names:
            _sqlite_check(root / database)
    required_originals = set(_listed_originals(root / "corpus.sqlite3"))
    if required_originals != {name for name in names if name.startswith("documents/")}:
        raise BackupError("Document blobs do not match the encrypted corpus index")
    for blob_name in required_originals:
        blob_path = root / blob_name
        _ensure_real_file(blob_path)
        with blob_path.open("rb") as fp:
            magic = fp.read(len(BLOB_MAGIC))
        if magic != BLOB_MAGIC or blob_path.stat().st_size <= len(BLOB_MAGIC) + 12:
            raise BackupError("Original encrypted document is incomplete")


def _sealed_blob(key: bytes, name: str, digest: str, data: bytes) -> bytes:
    aad = AAD_PREFIX + name.encode("utf-8") + b":" + digest.encode("ascii")
    return _encrypt(key, data, aad)


def _unseal_blob(key: bytes, name: str, digest: str, data: bytes) -> bytes:
    aad = AAD_PREFIX + name.encode("utf-8") + b":" + digest.encode("ascii")
    return _decrypt(key, data, aad)


def create_backup(home: Path, destination: Path, passphrase: str) -> dict[str, object]:
    """Make an encrypted backup with a *different* passphrase from the Keychain key.

    The archive carries encrypted SQLite snapshots and encrypted original blobs,
    but it DOES NOT carry the Keychain master key required to use them.
    """
    home = Path(home).expanduser()
    destination = Path(destination).expanduser()
    _ensure_safe_parent(destination)
    _check_new_target(destination)
    _check_not_below(destination, home)
    if len(passphrase) < 16:
        raise BackupError("Use an independent backup passphrase of at least 16 characters")
    with _offline_lock(home):
        with tempfile.TemporaryDirectory(prefix=".jafar-backup-work-", dir=destination.parent) as tmp:
            work = Path(tmp)
            os.chmod(work, 0o700)
            names: set[str] = set()
            for name in DATABASES:
                source = home / name
                if not source.exists():
                    if name in MANDATORY_DATABASES:
                        raise BackupError("Required local SQLite database is missing")
                    continue
                _snapshot_database(source, work / name)
                names.add(name)

            blobs = _listed_originals(work / "corpus.sqlite3")
            if len(blobs) + len(names) > MAX_MEMBERS:
                raise BackupError("Backup contains too many encrypted files")
            (work / "documents").mkdir(mode=0o700, exist_ok=True)
            for name in blobs:
                source = home / name
                _ensure_real_file(source)
                target = work / name
                with source.open("rb") as reader, target.open("xb") as writer:
                    while part := reader.read(1024 * 1024):
                        writer.write(part)
                os.chmod(target, 0o600)
                names.add(name)

            _validate_bundle_tree(work, names)
            salt = os.urandom(SALT_BYTES)
            key = _derive_key(passphrase, salt)
            manifest = {
                "format": FORMAT,
                "version": VERSION,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "files": [],
            }
            fd, archive_tmp = tempfile.mkstemp(
                prefix=".jafar-backup-", suffix=".tmp", dir=destination.parent
            )
            os.close(fd)
            archive_path = Path(archive_tmp)
            try:
                total = 0
                with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                    header = {
                        "format": FORMAT, "version": VERSION, "salt": salt.hex(),
                        "kdf": "scrypt-32768-8-1", "encryption": "AES-256-GCM",
                    }
                    archive.writestr(HEADER, json.dumps(header, separators=(",", ":")))
                    for index, name in enumerate(sorted(names)):
                        raw = (work / name).read_bytes()
                        total += len(raw)
                        if total > MAX_TOTAL_SIZE:
                            raise BackupError("Backup exceeds maximum supported beta archive size")
                        digest = hashlib.sha256(raw).hexdigest()
                        entry = f"{OBJECTS}{index:05d}.bin"
                        archive.writestr(entry, _sealed_blob(key, name, digest, raw))
                        manifest["files"].append(
                            {"path": name, "entry": entry, "size": len(raw), "sha256": digest}
                        )
                    manifest_bytes = json.dumps(
                        manifest, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                    if len(manifest_bytes) > MAX_MANIFEST_SIZE:
                        raise BackupError("Backup manifest is too large")
                    archive.writestr(
                        MANIFEST, _encrypt(key, manifest_bytes, AAD_PREFIX + b"manifest")
                    )
                with archive_path.open("rb") as fp:
                    os.fsync(fp.fileno())
                _check_new_target(destination)
                # A same-directory hard link installs the finished archive without
                # ever replacing a preexisting file, including a symlink.
                os.link(archive_path, destination, follow_symlinks=False)
                os.chmod(destination, 0o600)
                return {"files": len(names), "bytes": total, "location": str(destination)}
            finally:
                archive_path.unlink(missing_ok=True)


def _load_into_temp(archive_file: Path, passphrase: str, target: Path) -> dict[str, object]:
    _ensure_real_file(archive_file)
    with zipfile.ZipFile(archive_file, "r") as archive:
        all_members = archive.namelist()
        if len(all_members) != len(set(all_members)) or len(all_members) > MAX_MEMBERS + 2:
            raise BackupError("Unexpected or duplicated archive member")
        if HEADER not in all_members or MANIFEST not in all_members:
            raise BackupError("Backup header or manifest is missing")
        header_info = archive.getinfo(HEADER)
        manifest_info = archive.getinfo(MANIFEST)
        if header_info.file_size > 8192 or manifest_info.file_size > MAX_MANIFEST_SIZE + 32:
            raise BackupError("Backup metadata exceeds supported size")
        try:
            header = json.loads(archive.read(HEADER))
            if (
                header["format"] != FORMAT
                or header["version"] != VERSION
                or header["kdf"] != "scrypt-32768-8-1"
                or header["encryption"] != "AES-256-GCM"
            ):
                raise BackupError("Unsupported JAFAR backup format")
            salt = bytes.fromhex(header["salt"])
            if len(salt) != SALT_BYTES:
                raise BackupError("Invalid backup key derivation salt")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError("Invalid backup archive header") from exc
        key = _derive_key(passphrase, salt)
        manifest_raw = _decrypt(
            key, archive.read(MANIFEST), AAD_PREFIX + b"manifest"
        )
        try:
            manifest = json.loads(manifest_raw)
            if manifest["format"] != FORMAT or manifest["version"] != VERSION:
                raise BackupError("Invalid backup manifest identity")
            files = manifest["files"]
            if not isinstance(files, list) or not files or len(files) > MAX_MEMBERS:
                raise BackupError("Invalid backup file list")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BackupError("Invalid backup manifest") from exc

        expected_entries = {HEADER, MANIFEST}
        names: set[str] = set()
        total = 0
        for index, item in enumerate(files):
            try:
                name, entry = item["path"], item["entry"]
                size, digest = item["size"], item["sha256"]
            except (KeyError, TypeError) as exc:
                raise BackupError("Invalid backup file entry") from exc
            if (
                not isinstance(name, str)
                or not _allowed(name)
                or name in names
                or entry != f"{OBJECTS}{index:05d}.bin"
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or size > MAX_MEMBER_SIZE
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise BackupError("Invalid backup manifest file metadata")
            names.add(name)
            expected_entries.add(entry)
            if entry not in all_members or archive.getinfo(entry).file_size != size + 28:
                raise BackupError("Backup member size is inconsistent")
            total += size
            if total > MAX_TOTAL_SIZE:
                raise BackupError("Backup exceeds supported size")
            data = _unseal_blob(key, name, digest, archive.read(entry))
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                raise BackupError("Backup payload failed its integrity check")
            location = target / name
            location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with location.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(location, 0o600)

        if set(all_members) != expected_entries:
            raise BackupError("Unexpected content in encrypted backup")
        _validate_bundle_tree(target, names)
        return {"files": len(files), "bytes": total, "created_utc": manifest["created_utc"]}


def verify_backup(archive: Path, passphrase: str) -> dict[str, object]:
    """Authenticate archive, validate SQLite and check all indexed blob files.

    Not a test of the existing Keychain master key; that key is intentionally
    NOT stored in a portable backup.
    """
    archive = Path(archive).expanduser()
    try:
        with tempfile.TemporaryDirectory(prefix="jafar-backup-verify-") as tmp:
            os.chmod(tmp, 0o700)
            return _load_into_temp(archive, passphrase, Path(tmp))
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise BackupError("Backup archive cannot be verified") from exc


def restore_to_new_home(
    archive: Path, destination: Path, passphrase: str
) -> dict[str, object]:
    """Never overwrite an existing home. Verify fully before creating destination.

    The restored files remain encrypted using the ORIGINAL JAFAR Keychain
    master key. An independent backup passphrase is not a replacement for it.
    """
    destination = Path(destination).expanduser()
    _ensure_safe_parent(destination)
    _check_new_target(destination)
    with tempfile.TemporaryDirectory(
        prefix=".jafar-restore-verify-", dir=destination.parent
    ) as tmp:
        os.chmod(tmp, 0o700)
        staging = Path(tmp)
        result = _load_into_temp(Path(archive).expanduser(), passphrase, staging)
        # Exclusive creation fails even if another process creates target in the
        # interim. The restore never replaces any existing Matter archive.
        destination.mkdir(mode=0o700, exist_ok=False)
        try:
            for item in sorted(staging.iterdir(), key=lambda p: p.name):
                item.rename(destination / item.name)
            marker = destination / ".jafar-restore-ready"
            marker.write_text(
                "Staged encrypted copy. Requires original Keychain master key.\n",
                encoding="utf-8",
            )
            os.chmod(marker, 0o600)
            return {**result, "location": str(destination)}
        except Exception:
            # The destination was created exclusively by this operation.
            import shutil
            shutil.rmtree(destination)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JAFAR offline encrypted backups (app MUST be closed)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create a new encrypted backup")
    create.add_argument("--home", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify", help="Authenticate and inspect a backup")
    verify.add_argument("--archive", type=Path, required=True)
    restore = sub.add_parser("restore-new", help="Restore only to a nonexistent directory")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    password = getpass.getpass("Backup passphrase: ")
    if args.command == "create":
        repeated = getpass.getpass("Confirm backup passphrase: ")
        if repeated != password:
            parser.error("Passphrases do not match")
    try:
        if args.command == "create":
            info = create_backup(args.home, args.output, password)
        elif args.command == "verify":
            info = verify_backup(args.archive, password)
        else:
            info = restore_to_new_home(args.archive, args.target, password)
    except (BackupError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Backup operation failed: " + str(exc) + "\n")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

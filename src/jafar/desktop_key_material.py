"""One-shot desktop storage-key bootstrap for the frozen sidecar process."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .encrypted_sqlite_matter_repository import DesktopStorageError


_ENV_KEY = "JAFAR_DESKTOP_STORAGE_KEY"
_MATTER_INFO = b"jafar-desktop-matter-storage-v1"
_CORPUS_INFO = b"jafar-desktop-corpus-storage-v1"


@dataclass(frozen=True, slots=True)
class _DerivedKeys:
    matter: bytes
    corpus: bytes


_keys: _DerivedKeys | None = None
_bootstrap_attempted = False


def _derive(master_key: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=b"JAFAR desktop storage", info=info).derive(master_key)


def bootstrap_desktop_key_material() -> None:
    """Consume the Keychain master-key environment value once, then scrub it.

    Python cannot promise complete memory zeroization, but it never retains the raw
    key in a module global and best-effort clears the mutable decode buffer.
    """
    global _keys, _bootstrap_attempted
    if _bootstrap_attempted:
        raise DesktopStorageError("desktop storage key bootstrap was already attempted")
    _bootstrap_attempted = True
    encoded = os.environ.get(_ENV_KEY, "").strip()
    buffer = bytearray()
    try:
        if not encoded:
            raise DesktopStorageError("desktop storage key is unavailable")
        try:
            buffer.extend(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        except (ValueError, TypeError) as exc:
            raise DesktopStorageError("desktop storage key is invalid") from exc
        if len(buffer) != 32:
            raise DesktopStorageError("desktop storage key is invalid")
        master = bytes(buffer)
        _keys = _DerivedKeys(matter=_derive(master, _MATTER_INFO), corpus=_derive(master, _CORPUS_INFO))
    finally:
        os.environ.pop(_ENV_KEY, None)
        for index in range(len(buffer)):
            buffer[index] = 0


def desktop_matter_key() -> bytes:
    if _keys is None:
        raise DesktopStorageError("desktop storage key bootstrap is unavailable")
    return _keys.matter


def desktop_corpus_key() -> bytes:
    if _keys is None:
        raise DesktopStorageError("desktop storage key bootstrap is unavailable")
    return _keys.corpus

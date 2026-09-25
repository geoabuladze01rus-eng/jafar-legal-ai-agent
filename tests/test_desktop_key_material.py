from __future__ import annotations

import base64
import importlib
import os
import subprocess
import sys

import pytest

import jafar.desktop_key_material as key_material
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError


def _fresh():
    return importlib.reload(key_material)


def test_bootstrap_derives_separate_keys_and_scrubs_raw_environment(monkeypatch):
    module = _fresh()
    marker = b"m" * 32
    monkeypatch.setenv("JAFAR_DESKTOP_STORAGE_KEY", base64.urlsafe_b64encode(marker).decode().rstrip("="))
    module.bootstrap_desktop_key_material()
    assert "JAFAR_DESKTOP_STORAGE_KEY" not in os.environ
    assert module.desktop_matter_key() != module.desktop_corpus_key()


def test_bootstrap_fails_closed_and_scrubs_invalid_or_duplicate_key(monkeypatch):
    module = _fresh()
    monkeypatch.setenv("JAFAR_DESKTOP_STORAGE_KEY", "invalid")
    with pytest.raises(DesktopStorageError):
        module.bootstrap_desktop_key_material()
    assert "JAFAR_DESKTOP_STORAGE_KEY" not in os.environ
    with pytest.raises(DesktopStorageError):
        module.bootstrap_desktop_key_material()


def test_scrubbed_key_is_not_inherited_by_subprocess(monkeypatch):
    module = _fresh()
    monkeypatch.setenv("JAFAR_DESKTOP_STORAGE_KEY", base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("="))
    module.bootstrap_desktop_key_material()
    result = subprocess.run(
        [sys.executable, "-c", "import os; raise SystemExit(int('JAFAR_DESKTOP_STORAGE_KEY' in os.environ))"],
        check=False,
    )
    assert result.returncode == 0

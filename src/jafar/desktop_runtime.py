"""Safe runtime primitives used only by the bundled macOS sidecar.

This module deliberately has no dependency on the source checkout or a developer
environment.  It is also useful in tests, where a temporary home can be supplied
through ``JAFAR_DESKTOP_HOME``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


RUNTIME_MODE = "desktop"
LOOPBACK_HOST = "127.0.0.1"


@dataclass(frozen=True)
class DesktopPaths:
    application_support: Path
    logs: Path
    cache: Path
    temporary: Path

    @property
    def matter_database(self) -> Path:
        return self.application_support / "matters.sqlite3"

    @property
    def database_lock(self) -> Path:
        return self.application_support / "matters.lock"

    def create(self) -> "DesktopPaths":
        for path in (self.application_support, self.logs, self.cache, self.temporary):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                # Best effort only: the process may run on a filesystem without POSIX modes.
                pass
        return self


def desktop_paths(home: Path | None = None) -> DesktopPaths:
    """Return app-owned mutable paths without writing inside JAFAR.app."""

    configured_home = os.getenv("JAFAR_DESKTOP_HOME", "").strip()
    root = home or (
        Path(configured_home).expanduser()
        if configured_home
        else Path.home() / "Library" / "Application Support" / "JAFAR"
    )
    return DesktopPaths(
        application_support=root,
        logs=Path.home() / "Library" / "Logs" / "JAFAR" if home is None else root / "Logs",
        cache=Path.home() / "Library" / "Caches" / "JAFAR" if home is None else root / "Caches",
        temporary=(root / "Temporary"),
    )


def is_desktop_runtime() -> bool:
    return os.getenv("JAFAR_RUNTIME_MODE", "").strip().lower() == RUNTIME_MODE

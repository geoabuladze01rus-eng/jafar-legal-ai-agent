"""Safe, content-free desktop diagnostic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+|token=|api[_-]?key=|secret=)[^\s,;]+")


def redact_diagnostic(value: str) -> str:
    return _SECRET_PATTERN.sub(r"\1[REDACTED]", value)


@dataclass(frozen=True)
class DesktopDiagnostic:
    app_version: str
    backend_state: str
    storage_state: str
    ollama_state: str
    model_state: str

    def render(self) -> str:
        return "\n".join(
            (
                f"JAFAR version: {redact_diagnostic(self.app_version)}",
                f"Local engine: {redact_diagnostic(self.backend_state)}",
                f"Local storage: {redact_diagnostic(self.storage_state)}",
                f"Ollama: {redact_diagnostic(self.ollama_state)}",
                f"Model: {redact_diagnostic(self.model_state)}",
            )
        )

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OCRResult:
    text: str
    provider: str
    confidence: float | None = None


class OCRProvider:
    """Explicit OCR boundary. A production provider is injected here."""

    name = "unconfigured"

    def recognize(self, path: Path) -> OCRResult:
        raise NotImplementedError("OCR provider is not configured")


class UnconfiguredOCRProvider(OCRProvider):
    def recognize(self, path: Path) -> OCRResult:
        raise RuntimeError(
            f"OCR is required for {path.name}, but no OCR provider is configured"
        )

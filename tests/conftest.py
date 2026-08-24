from base64 import b64decode
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def synthetic_pdf_bytes() -> bytes:
    encoded = (FIXTURES / "synthetic_legal_document.pdf.b64").read_text(encoding="ascii")
    return b64decode(encoded)


@pytest.fixture
def synthetic_legal_text() -> str:
    return (FIXTURES / "synthetic_legal_document.txt").read_text(encoding="utf-8")

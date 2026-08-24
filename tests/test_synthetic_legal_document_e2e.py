from jafar.document_intake import DocumentExtractor
from jafar.document_intelligence import DocumentIntelligence
from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer


def test_synthetic_pdf_to_mocked_ocr_and_legal_analysis(
    synthetic_pdf_bytes: bytes,
    synthetic_legal_text: str,
) -> None:
    ingested = DocumentExtractor().extract(
        "synthetic-legal-document.pdf",
        synthetic_pdf_bytes,
        "application/pdf",
    )
    assert ingested.text == "Synthetic legal document fixture; no personal data."
    assert len(ingested.fingerprint) == 64

    # The fixture sidecar is the deterministic OCR mock. No provider or real legal
    # document is used by this test.
    normalized = DocumentIntelligence().extract(
        document_id="synthetic-document-1",
        text=synthetic_legal_text,
        metadata={"source": "ocr_mock", "fixture": True},
    )
    analysis = LegalAnalyzer().analyze(
        normalized.text,
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.CRIMINAL,
    )

    assert normalized.document_id == "synthetic-document-1"
    assert normalized.metadata == {"source": "ocr_mock", "fixture": True}
    assert "99-000001/2026" in " ".join(analysis.key_facts)
    assert any(issue.risk.value == "high" for issue in analysis.issues)
    assert {deadline.due_date.isoformat() for deadline in analysis.deadlines} >= {
        "2026-08-24",
        "2026-08-25",
    }
    assert "Противоречие" in normalized.text
    assert "приложение № 3" in normalized.text

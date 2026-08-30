from __future__ import annotations

from jafar.case_law_document import CaseLawDocument
from jafar.legal_proposition_extractor import LegalPropositionExtractor


def make_document(text: str) -> CaseLawDocument:
    return CaseLawDocument(
        url="https://example.test/case",
        text=text,
        raw_fingerprint="raw",
        text_fingerprint="text-fp",
        content_type="text/html",
        etag=None,
        last_modified=None,
    )


def test_extracts_statute_reference_as_candidate() -> None:
    enrichment = LegalPropositionExtractor().extract(
        make_document("Суд указал, что требования ст. 75 УПК РФ подлежат проверке при оценке доказательства.")
    )

    assert any("75 УПК РФ" in item.raw_text for item in enrichment.legal_reference_candidates)
    assert enrichment.requires_human_review is True


def test_extracts_proposition_candidate_without_verifying_it() -> None:
    enrichment = LegalPropositionExtractor().extract(
        make_document(
            "Верховный Суд указал, что доказательство не может использоваться без проверки источника его происхождения."
        )
    )

    assert len(enrichment.proposition_candidates) == 1
    candidate = enrichment.proposition_candidates[0]
    assert candidate.confidence <= 0.55
    assert enrichment.requires_human_review is True


def test_detects_candidate_topics_without_promoting_legal_truth() -> None:
    enrichment = LegalPropositionExtractor().extract(
        make_document(
            "При решении вопроса о мере пресечения суд исследовал домашний арест и достаточность доказательств."
        )
    )

    assert "меры пресечения" in enrichment.topic_candidates
    assert "оценка доказательств" in enrichment.topic_candidates


def test_invalid_dates_are_ignored() -> None:
    enrichment = LegalPropositionExtractor().extract(
        make_document("Рассмотрено 31.02.2026 и повторно 28.08.2026.")
    )

    assert [item.isoformat() for item in enrichment.date_candidates] == ["2026-08-28"]

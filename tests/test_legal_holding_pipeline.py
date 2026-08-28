from jafar.legal_holding_pipeline import LegalHoldingPipeline
from jafar.legal_proposition_extractor import CaseLawEnrichment, PropositionCandidate


def enrichment(*texts: str) -> CaseLawEnrichment:
    return CaseLawEnrichment(
        citation_candidates=(),
        date_candidates=(),
        legal_reference_candidates=(),
        topic_candidates=(),
        proposition_candidates=tuple(
            PropositionCandidate(text=text, confidence=0.55, rationale="test") for text in texts
        ),
        document_text_fingerprint="abc",
        requires_human_review=True,
    )


def test_pipeline_promotes_only_verified_holding() -> None:
    report = LegalHoldingPipeline().run(
        enrichment(
            "Судебная коллегия указала, что не допускается ограничение права на защиту без предусмотренных законом оснований.",
            "Защитник указал, что вывод суда первой инстанции является ошибочным и подлежит отмене.",
        )
    )
    assert len(report.accepted_texts) == 1
    assert len(report.blocked_texts) == 1
    assert report.may_enter_precedent_pipeline is True
    assert report.requires_human_review is True


def test_pipeline_blocks_document_without_verified_holding() -> None:
    report = LegalHoldingPipeline().run(
        enrichment("Прокурор указал, что судебные решения являются законными и обоснованными.")
    )
    assert report.accepted_texts == ()
    assert report.may_enter_precedent_pipeline is False
    assert report.requires_human_review is True

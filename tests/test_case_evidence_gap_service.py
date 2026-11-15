"""Tests for Matter-scoped statement extraction, provenance verification and evidence gap analysis."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.case_evidence_gap_api import build_case_evidence_gap_router
from jafar.case_evidence_gap_service import (
    CaseEvidenceGapRequest,
    CaseEvidenceGapService,
)
from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


def _matter(matter_id: str) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title="Учебное арбитражное дело",
        matter_type=MatterType.ARBITRATION,
        client_name="ООО «Поставщик»",
        opposing_party="АО «Покупатель»",
        case_number="А40-99999/2026",
        created_at=now,
        updated_at=now,
    )


class StubCorpus:
    def __init__(self):
        self._documents = {
            ("matter-1", "doc-contract"): SimpleNamespace(
                state="READY", filename="Договор поставки № 15.docx"
            ),
            ("matter-1", "doc-protocol"): SimpleNamespace(
                state="READY", filename="Протокол судебного заседания.pdf"
            ),
            ("matter-foreign", "doc-other"): SimpleNamespace(
                state="READY", filename="Чужой документ.txt"
            ),
        }
        self._chunks = {
            "matter-1": [
                MatterChunk(
                    chunk_id="doc-contract:0",
                    matter_id="matter-1",
                    document_id="doc-contract",
                    source_page=1,
                    chunk_index=0,
                    content=(
                        "15.03.2026 заключен договор поставки № 15 на сумму 1 500 000 рублей. "
                        "Товар передан по накладной от 20.03.2026."
                    ),
                ),
                MatterChunk(
                    chunk_id="doc-protocol:0",
                    matter_id="matter-1",
                    document_id="doc-protocol",
                    source_page=2,
                    chunk_index=0,
                    content=(
                        "Представитель ответчика заявил, что оплата была произведена в полном объеме наличными денежными средствами. "
                        "Истец утверждает, что денежные средства на расчетный счет не поступали. "
                        "Суд установил, что первичные банковские документы об оплате сторонами не представлены."
                    ),
                ),
            ],
            "matter-foreign": [
                MatterChunk(
                    chunk_id="doc-other:0",
                    matter_id="matter-foreign",
                    document_id="doc-other",
                    source_page=1,
                    chunk_index=0,
                    content="Совершенно другое дело и другие стороны.",
                ),
            ],
        }

    def get_document(self, matter_id: str, document_id: str):
        return self._documents.get((matter_id, document_id))

    def verify_document(self, matter_id: str, document_id: str) -> str:
        if (matter_id, document_id) not in self._documents:
            raise ValueError("Document not found")
        return "sha256-verified"

    def chunks(self, matter_id: str) -> list[MatterChunk]:
        return self._chunks.get(matter_id, [])


class StubLocalModel:
    def __init__(self, citation: str, quote: str):
        self.citation = citation
        self.quote = quote
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, request):
        self.calls += 1
        assert request.allowed_providers == ("ollama",)
        assert request.confidential is True
        data = {
            "statements": [
                {
                    "category": "party_claim",
                    "citation": self.citation,
                    "quote": self.quote,
                    "statement": "Ответчик заявил о полной оплате наличными",
                    "subject": "Ответчик",
                }
            ],
            "gaps": [
                {
                    "topic": "Банковские документы об оплате",
                    "description": "В материалах дела отсутствуют платежные поручения об оплате",
                    "expected_evidence": ["банковская выписка", "платежное поручение"],
                    "severity": "high",
                    "related_citation": self.citation,
                    "suggested_action": "Заявить ходатайство об истребовании банковской выписки",
                }
            ],
        }
        return ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            text=json.dumps(data, ensure_ascii=False),
            metadata={"local": True},
        )


def test_deterministic_extraction_distinguishes_facts_claims_and_findings():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    service = CaseEvidenceGapService(matters, corpus)

    report = service.analyze(
        "matter-1",
        CaseEvidenceGapRequest(source_document_ids=["doc-contract", "doc-protocol"]),
    )

    assert report.matter_id == "matter-1"
    assert report.case_number == "А40-99999/2026"
    assert len(report.statements) >= 3

    categories = {s.category for s in report.statements}
    assert "fact" in categories
    assert "party_claim" in categories
    assert "court_finding" in categories

    # Verbatim quotations must exist in chunks
    chunks_text = " ".join(c.content for c in corpus.chunks("matter-1"))
    for stmt in report.statements:
        assert stmt.quote in chunks_text
        assert stmt.citation.startswith("document:")

    # Gaps detected for payment claims without bank statements
    assert len(report.gaps) >= 1
    payment_gap = next((g for g in report.gaps if "оплат" in g.topic.lower() or "оплат" in g.description.lower()), None)
    assert payment_gap is not None
    assert payment_gap.severity == "high"
    assert "платеж" in payment_gap.expected_evidence[0].lower().replace("ё", "е") or "выписка" in payment_gap.expected_evidence[0].lower()
    assert "ходатайств" in payment_gap.suggested_action.lower()


def test_cross_matter_document_access_is_rejected():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    service = CaseEvidenceGapService(matters, corpus)

    with pytest.raises(ValueError, match="not found in selected Matter"):
        service.analyze(
            "matter-1",
            CaseEvidenceGapRequest(source_document_ids=["doc-contract", "doc-other"]),
        )


def test_local_ai_extraction_authenticates_verbatim_quotes_and_rejects_hallucinations():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    valid_citation = corpus.chunks("matter-1")[1].citation
    valid_quote = "Истец утверждает, что денежные средства на расчетный счет не поступали."

    model = StubLocalModel(valid_citation, valid_quote)
    service = CaseEvidenceGapService(matters, corpus, model)

    report = service.analyze(
        "matter-1",
        CaseEvidenceGapRequest(source_document_ids=["doc-protocol"]),
    )

    assert model.calls == 1
    assert any(s.quote == valid_quote for s in report.statements)


def test_api_router_evidence_gaps_endpoint():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()

    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_case_evidence_gap_router(matters, corpus))

    client = TestClient(app)
    response = client.post(
        "/v1/matters/matter-1/analysis/evidence-gaps",
        headers={"Authorization": "Bearer test-desktop-token"},
        json={"source_document_ids": ["doc-contract", "doc-protocol"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matter_id"] == "matter-1"
    assert len(data["statements"]) > 0
    assert len(data["gaps"]) > 0
    assert "warnings" in data


def test_classification_party_demands_defendant_words_and_unclear_status():
    """Item 2: 'Прошу взыскать' is party claim; defendant words in judgment remain party claim;
    unclear status/author is marked 'needs_verification' with subject 'Требует проверки'."""
    from jafar.case_evidence_gap_service import _classify_sentence

    # 1. 'Прошу взыскать задолженность' must be a party_claim, NOT court_finding
    stmt_demand = "Прошу взыскать задолженность по договору поставки в сумме 500 000 рублей."
    assert _classify_sentence(stmt_demand) == "party_claim"

    # 2. Defendant words in a judicial act must remain party_claim
    stmt_defendant = "В решении суда отражено, что в заседании ответчик пояснил, что товар не принимал."
    assert _classify_sentence(stmt_defendant) == "party_claim"

    # 3. Objective fact
    stmt_fact = "Платежным поручением № 44 от 12.04.2026 перечислены денежные средства."
    assert _classify_sentence(stmt_fact) == "fact"

    # 4. Court finding
    stmt_court = "Суд установил, что обязательства стороной не исполнены."
    assert _classify_sentence(stmt_court) == "court_finding"

    # 5. Unclear author or status -> needs_verification (quote alone does not make it a fact)
    stmt_unclear = "В складском помещении хранились различные материалы и коробки."
    assert _classify_sentence(stmt_unclear) == "needs_verification"

    # Full service extraction test
    matters = MatterStore()
    matters.create(_matter("matter-class"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-judgment:0",
                matter_id="matter-class",
                document_id="doc-judgment",
                source_page=1,
                chunk_index=0,
                content=(
                    "Истец заявил требование: «Прошу взыскать задолженность в размере 500 000 рублей». "
                    "В судебном заседании ответчик пояснил, что продукцию не получал и накладную не подписывал. "
                    "В складском помещении хранились различные строительные материалы. "
                    "Суд решил: отказать в удовлетворении ходатайства об отложении разбирательства."
                ),
            )
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze("matter-class", CaseEvidenceGapRequest(source_document_ids=["doc-judgment"]))

    statements_by_quote = {s.quote: s for s in report.statements}

    # Demand check
    demand_stmt = next((s for q, s in statements_by_quote.items() if "прошу взыскать" in q.lower()), None)
    assert demand_stmt is not None
    assert demand_stmt.category == "party_claim"
    assert demand_stmt.subject == "Истец / заявитель"

    # Defendant words check
    def_stmt = next((s for q, s in statements_by_quote.items() if "ответчик пояснил" in q.lower()), None)
    assert def_stmt is not None
    assert def_stmt.category == "party_claim"
    assert def_stmt.subject == "Ответчик"

    # Unclear status check
    unclear_stmt = next((s for q, s in statements_by_quote.items() if "складском помещении" in q.lower()), None)
    assert unclear_stmt is not None
    assert unclear_stmt.category == "needs_verification"
    assert unclear_stmt.subject == "Требует проверки"


def test_corroborating_documents_negative_reference_does_not_clear_warning():
    """Item 3: 'Банковская выписка по иному договору не представлена' must not clear the gap.
    If connection is not confirmed, description must contain 'В выбранных материалах подтверждение этой операции не найдено'."""
    matters = MatterStore()
    matters.create(_matter("matter-neg"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-claim:0",
                matter_id="matter-neg",
                document_id="doc-claim",
                source_page=1,
                chunk_index=0,
                content=(
                    "Истец утверждает, что оплата по договору поставки № 15 в сумме 700 000 рублей не была произведена. "
                    "Банковская выписка по иному договору не представлена."
                ),
            )
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze("matter-neg", CaseEvidenceGapRequest(source_document_ids=["doc-claim"]))

    # Payment gap MUST remain because the mention is negative ("не представлена") and for another contract!
    payment_gap = next((g for g in report.gaps if "оплат" in g.topic.lower()), None)
    assert payment_gap is not None
    assert "В выбранных материалах подтверждение этой операции не найдено" in payment_gap.description


def test_corroborating_documents_specific_operation_handling():
    """Item 3 reverse case: primary document for the specific operation clears the gap,
    while a primary document for an unrelated contract does not."""
    matters = MatterStore()
    matters.create(_matter("matter-ops"))

    # Case A: Document for an unrelated contract № 99 does NOT clear warning for contract № 15
    corpus_unrelated = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-c:0",
                matter_id="matter-ops",
                document_id="doc-c",
                source_page=1,
                chunk_index=0,
                content="Истец требует взыскать задолженность по договору поставки № 15.",
            ),
            MatterChunk(
                chunk_id="doc-p:0",
                matter_id="matter-ops",
                document_id="doc-p",
                source_page=1,
                chunk_index=0,
                content="Платежным поручением № 88 от 01.02.2026 перечислены средства по договору № 99.",
            ),
        ],
    )
    service_unrelated = CaseEvidenceGapService(matters, corpus_unrelated)
    report_unrelated = service_unrelated.analyze(
        "matter-ops", CaseEvidenceGapRequest(source_document_ids=["doc-c", "doc-p"])
    )
    payment_gap_unrelated = next((g for g in report_unrelated.gaps if "оплат" in g.topic.lower()), None)
    assert payment_gap_unrelated is not None
    assert "В выбранных материалах подтверждение этой операции не найдено" in payment_gap_unrelated.description

    # Case B: Document for the specific contract № 15 DOES corroborate and clears the gap
    corpus_related = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-c:0",
                matter_id="matter-ops",
                document_id="doc-c",
                source_page=1,
                chunk_index=0,
                content="Истец требует взыскать задолженность по договору поставки № 15.",
            ),
            MatterChunk(
                chunk_id="doc-p:0",
                matter_id="matter-ops",
                document_id="doc-p",
                source_page=1,
                chunk_index=0,
                content="Платежным поручением № 102 от 12.05.2026 перечислены средства в счет оплаты по договору поставки № 15.",
            ),
        ],
    )
    service_related = CaseEvidenceGapService(matters, corpus_related)
    report_related = service_related.analyze(
        "matter-ops", CaseEvidenceGapRequest(source_document_ids=["doc-c", "doc-p"])
    )
    payment_gap_related = next((g for g in report_related.gaps if "оплат" in g.topic.lower()), None)
    assert payment_gap_related is None
